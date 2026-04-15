from __future__ import annotations

import logging
from datetime import datetime
from time import monotonic

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import Settings
from constants import (
    BOT_BUTTON_TEXT,
    COOLDOWN_MESSAGE,
    GENERIC_ERROR_MESSAGE,
    UNKNOWN_MESSAGE,
    USER_REQUEST_COOLDOWN_SECONDS,
)
from formatter import format_daily_menu, format_stats_report, split_message
from menu_service import MenuService
from scheduler import DailyMenuScheduler
from stats_service import StatsService

LOGGER = logging.getLogger(__name__)


def build_application(settings: Settings, menu_service: MenuService, stats_service: StatsService) -> Application:
    scheduler_holder: dict[str, DailyMenuScheduler] = {}

    async def post_init(application: Application) -> None:
        scheduler = DailyMenuScheduler(
            bot=application.bot,
            menu_service=menu_service,
            settings=settings,
            stats_service=stats_service,
        )
        scheduler_holder["scheduler"] = scheduler
        application.bot_data["scheduler"] = scheduler
        scheduler.start()
        LOGGER.info("Telegram application initialized.")

    async def post_shutdown(application: Application) -> None:
        del application
        scheduler = scheduler_holder.get("scheduler")
        if scheduler is not None:
            scheduler.shutdown()

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.bot_data["menu_service"] = menu_service
    application.bot_data["stats_service"] = stats_service
    application.bot_data["settings"] = settings
    application.bot_data["user_request_times"] = {}

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.Regex(f"^{BOT_BUTTON_TEXT}$"), todays_halal_menu))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_text_message))
    application.add_error_handler(error_handler)
    return application


def build_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BOT_BUTTON_TEXT)]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_in_chunks(
        update,
        UNKNOWN_MESSAGE,
        include_keyboard=True,
        message_type="other_response",
        context=context,
    )


async def todays_halal_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    menu_service: MenuService = context.application.bot_data["menu_service"]
    now = datetime.now(settings.timezone)

    if _is_rate_limited(update, context):
        await _reply_in_chunks(
            update,
            COOLDOWN_MESSAGE,
            include_keyboard=True,
            message_type="other_response",
            context=context,
            sent_at=now,
        )
        return

    try:
        snapshot = await menu_service.get_today_halal_menu(now)
        message = format_daily_menu(snapshot, now)
    except Exception:
        LOGGER.exception("Failed to build today's halal menu message.")
        message = GENERIC_ERROR_MESSAGE

    await _reply_in_chunks(
        update,
        message,
        include_keyboard=True,
        message_type="manual_menu",
        context=context,
        sent_at=now,
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not _is_admin(update, settings):
        return

    stats_service: StatsService = context.application.bot_data["stats_service"]
    now = datetime.now(settings.timezone)
    report = await stats_service.build_report(now.date())
    message = format_stats_report(report, "Today")
    await _reply_in_chunks(
        update,
        message,
        include_keyboard=True,
        message_type="other_response",
        context=context,
        sent_at=now,
    )


async def unknown_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    now = datetime.now(settings.timezone)
    await _reply_in_chunks(
        update,
        UNKNOWN_MESSAGE,
        include_keyboard=True,
        message_type="other_response",
        context=context,
        sent_at=now,
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.exception("Unhandled Telegram update error.", exc_info=context.error)
    if not isinstance(update, Update):
        return
    settings: Settings = context.application.bot_data["settings"]
    now = datetime.now(settings.timezone)
    try:
        await _reply_in_chunks(
            update,
            GENERIC_ERROR_MESSAGE,
            include_keyboard=True,
            message_type="error_response",
            context=context,
            sent_at=now,
        )
    except Exception:
        LOGGER.exception("Failed to send fallback error message.")


def _is_rate_limited(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if user is None:
        return False

    request_times: dict[int, float] = context.application.bot_data["user_request_times"]
    now_monotonic = monotonic()
    previous = request_times.get(user.id)
    request_times[user.id] = now_monotonic
    return previous is not None and now_monotonic - previous < USER_REQUEST_COOLDOWN_SECONDS


def _is_admin(update: Update, settings: Settings) -> bool:
    if update.effective_chat is not None and update.effective_chat.id == settings.admin_chat_id:
        return True
    return settings.admin_user_id is not None and update.effective_user is not None and update.effective_user.id == settings.admin_user_id


async def _reply_in_chunks(
    update: Update,
    text: str,
    *,
    include_keyboard: bool,
    message_type: str,
    context: ContextTypes.DEFAULT_TYPE,
    sent_at: datetime | None = None,
) -> None:
    if update.effective_message is None or update.effective_chat is None:
        return

    settings: Settings = context.application.bot_data["settings"]
    stats_service: StatsService = context.application.bot_data["stats_service"]
    timestamp = sent_at or datetime.now(settings.timezone)
    chunks = split_message(text)
    for index, chunk in enumerate(chunks):
        reply_markup = build_reply_keyboard() if include_keyboard and index == len(chunks) - 1 else None
        try:
            await update.effective_message.reply_text(chunk, reply_markup=reply_markup)
        except Exception as exc:
            await stats_service.log_message_attempt(
                chat_id=update.effective_chat.id,
                message_type=message_type,
                success=False,
                sent_at=timestamp,
                event_date=timestamp.date(),
                failure_reason=str(exc),
            )
            raise

        await stats_service.log_message_attempt(
            chat_id=update.effective_chat.id,
            message_type=message_type,
            success=True,
            sent_at=timestamp,
            event_date=timestamp.date(),
        )
