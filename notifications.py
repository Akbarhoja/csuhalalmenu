from __future__ import annotations

import logging
from datetime import datetime

from telegram import Bot, Update

from config import Settings

LOGGER = logging.getLogger(__name__)


class AdminNotificationService:
    def __init__(self, *, bot: Bot, settings: Settings) -> None:
        self._bot = bot
        self._settings = settings

    async def notify_manual_usage(self, update: Update, *, action: str, now: datetime) -> None:
        user = update.effective_user
        chat = update.effective_chat
        if user is None or chat is None:
            return

        full_name = self._build_full_name(
            first_name=user.first_name,
            last_name=user.last_name,
        )
        username = f"@{user.username}" if user.username else "N/A"
        message = (
            "This user used the bot:\n"
            f"- Name: {full_name}\n"
            f"- Username: {username}\n"
            f"- User ID: {user.id}\n"
            f"- Chat ID: {chat.id}\n"
            f"- Time: {now.strftime('%B %d, %Y %I:%M %p %Z')}\n"
            f"- Action: {action}"
        )

        try:
            await self._bot.send_message(chat_id=self._settings.admin_chat_id, text=message)
        except Exception:
            LOGGER.exception(
                "Failed to send admin usage notification for user_id=%s chat_id=%s.",
                user.id,
                chat.id,
            )

    def _build_full_name(self, *, first_name: str | None, last_name: str | None) -> str:
        parts = [part.strip() for part in (first_name, last_name) if part and part.strip()]
        return " ".join(parts) if parts else "N/A"
