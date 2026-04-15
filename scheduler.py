from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

from config import Settings
from formatter import format_daily_menu, split_message
from menu_service import MenuService
from stats_service import StatsService

LOGGER = logging.getLogger(__name__)


class DailyMenuScheduler:
    def __init__(
        self,
        *,
        bot: Bot,
        menu_service: MenuService,
        settings: Settings,
        stats_service: StatsService,
    ) -> None:
        self._bot = bot
        self._menu_service = menu_service
        self._settings = settings
        self._stats_service = stats_service
        self._scheduler = AsyncIOScheduler(timezone=settings.timezone)

    def start(self) -> None:
        if self._scheduler.running:
            return

        trigger = CronTrigger(
            hour=self._settings.daily_send_hour,
            minute=self._settings.daily_send_minute,
            timezone=self._settings.timezone,
        )
        self._scheduler.add_job(
            self._send_daily_menu,
            trigger=trigger,
            id="daily-halal-menu",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=1800,
        )
        self._scheduler.start()
        LOGGER.info(
            "Daily scheduler started for %02d:%02d %s.",
            self._settings.daily_send_hour,
            self._settings.daily_send_minute,
            self._settings.timezone_name,
        )

    def shutdown(self) -> None:
        if not self._scheduler.running:
            return
        self._scheduler.shutdown(wait=False)
        LOGGER.info("Daily scheduler stopped.")

    async def _send_daily_menu(self) -> None:
        now = datetime.now(self._settings.timezone)
        try:
            snapshot = await self._menu_service.refresh_today_halal_menu(now)
            message = format_daily_menu(snapshot, now)
        except Exception:
            LOGGER.exception("Scheduled daily menu generation failed.")
            return

        for chunk in split_message(message):
            try:
                await self._bot.send_message(chat_id=self._settings.telegram_chat_id, text=chunk)
            except Exception as exc:
                await self._stats_service.log_message_attempt(
                    chat_id=self._settings.telegram_chat_id,
                    message_type="scheduled_daily",
                    success=False,
                    sent_at=now,
                    event_date=now.date(),
                    failure_reason=str(exc),
                )
                LOGGER.exception("Scheduled daily halal menu send failed.")
                return

            await self._stats_service.log_message_attempt(
                chat_id=self._settings.telegram_chat_id,
                message_type="scheduled_daily",
                success=True,
                sent_at=now,
                event_date=now.date(),
            )

        LOGGER.info("Sent scheduled halal menu message to chat %s.", self._settings.telegram_chat_id)
