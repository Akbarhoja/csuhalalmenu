from __future__ import annotations

import logging
from datetime import datetime

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import Settings
from constants import BOT_BUTTON_TEXT
from formatter import format_daily_menu
from menu_service import MenuService
from scheduler import DailyMenuScheduler

LOGGER = logging.getLogger(__name__)


def build_application(settings: Settings, menu_service: MenuService) -> Application:
    scheduler_holder: dict[str, DailyMenuScheduler] = {}

    async def post_init(application: Application) -> None:
        scheduler = DailyMenuScheduler(bot=application.bot, menu_service=menu_service, settings=settings)
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
    application.bot_data["settings"] = settings

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.Regex(f"^{BOT_BUTTON_TEXT}$"), todays_halal_menu))
    return application


def build_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BOT_BUTTON_TEXT)]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.effective_message is None:
        return

    await update.effective_message.reply_text(
        "Press the button below to check today's halal menu.",
        reply_markup=build_reply_keyboard(),
    )


async def todays_halal_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return

    settings: Settings = context.application.bot_data["settings"]
    menu_service: MenuService = context.application.bot_data["menu_service"]
    now = datetime.now(settings.timezone)

    try:
        snapshot = await menu_service.get_today_halal_menu(now)
        message = format_daily_menu(snapshot, now)
    except Exception:
        LOGGER.exception("Failed to build today's halal menu message.")
        message = "Meow, meow! I couldn't check the halal menu right now. Please try again soon."

    await update.effective_message.reply_text(
        message,
        reply_markup=build_reply_keyboard(),
    )
