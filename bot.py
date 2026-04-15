from __future__ import annotations

import logging
from datetime import datetime
from time import monotonic

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import Settings
from constants import (
    BOT_BUTTON_TEXT,
    COOLDOWN_MESSAGE,
    GENERIC_ERROR_MESSAGE,
    UNKNOWN_MESSAGE,
    USER_REQUEST_COOLDOWN_SECONDS,
)
from formatter import format_daily_menu, split_message
from menu_service import MenuService
from notifications import AdminNotificationService

LOGGER = logging.getLogger(__name__)


def build_application(settings: Settings, menu_service: MenuService) -> Application:
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .concurrent_updates(True)
        .build()
    )

    application.bot_data["menu_service"] = menu_service
    application.bot_data["settings"] = settings
    application.bot_data["user_request_times"] = {}
    application.bot_data["notification_service"] = AdminNotificationService(
        bot=application.bot,
        settings=settings,
    )

    LOGGER.info("Telegram application initialized.")

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.Regex(r"(?i)^\s*todays halal menu\s*$"), todays_halal_menu))
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
        context=context,
    )


async def todays_halal_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    menu_service: MenuService = context.application.bot_data["menu_service"]
    notification_service: AdminNotificationService = context.application.bot_data["notification_service"]
    now = datetime.now(settings.timezone)
    user = update.effective_user
    chat = update.effective_chat

    if _is_rate_limited(update, context):
        await _reply_in_chunks(
            update,
            COOLDOWN_MESSAGE,
            include_keyboard=True,
            context=context,
            sent_at=now,
        )
        return

    LOGGER.info(
        "Halal menu request started. user_id=%s chat_id=%s",
        user.id if user is not None else "unknown",
        chat.id if chat is not None else "unknown",
    )

    if chat is not None:
        try:
            await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)
        except Exception:
            LOGGER.debug("Failed to send typing action for chat_id=%s.", chat.id, exc_info=True)

    try:
        snapshot = await menu_service.get_today_halal_menu(now)
        message = format_daily_menu(snapshot, now)
        LOGGER.info(
            "Halal menu request succeeded. user_id=%s chat_id=%s cached_at=%s",
            user.id if user is not None else "unknown",
            chat.id if chat is not None else "unknown",
            snapshot.fetched_at.isoformat(),
        )
    except Exception:
        LOGGER.exception("Failed to build today's halal menu message.")
        message = GENERIC_ERROR_MESSAGE

    try:
        await _reply_in_chunks(
            update,
            message,
            include_keyboard=True,
            context=context,
            sent_at=now,
        )
    except Exception:
        LOGGER.exception(
            "Failed to send halal menu response. user_id=%s chat_id=%s",
            user.id if user is not None else "unknown",
            chat.id if chat is not None else "unknown",
        )
        return

    await notification_service.notify_manual_usage(
        update,
        action="Requested Today's Halal Menu",
        now=now,
    )


async def unknown_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_in_chunks(
        update,
        UNKNOWN_MESSAGE,
        include_keyboard=True,
        context=context,
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


async def _reply_in_chunks(
    update: Update,
    text: str,
    *,
    include_keyboard: bool,
    context: ContextTypes.DEFAULT_TYPE,
    sent_at: datetime | None = None,
) -> None:
    del context, sent_at
    if update.effective_message is None:
        return

    chunks = split_message(text)
    for index, chunk in enumerate(chunks):
        reply_markup = build_reply_keyboard() if include_keyboard and index == len(chunks) - 1 else None
        await update.effective_message.reply_text(chunk, reply_markup=reply_markup)
    LOGGER.info("Sent %s response chunk(s).", len(chunks))
