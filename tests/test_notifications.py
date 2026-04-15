from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from config import Settings
from notifications import AdminNotificationService


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send_message(self, *, chat_id: int, text: str) -> None:
        self.messages.append({"chat_id": chat_id, "text": text})


def test_admin_notification_service_formats_manual_usage_message() -> None:
    fake_bot = FakeBot()
    settings = Settings(
        telegram_bot_token="token",
        timezone_name="America/Denver",
        timezone=ZoneInfo("America/Denver"),
        port=10000,
        webhook_base_url=None,
        use_webhook=False,
        admin_chat_id=999,
    )
    service = AdminNotificationService(bot=fake_bot, settings=settings)
    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            first_name="Akbar",
            last_name="Khadjaev",
            username="a_khadjaev",
            id=456,
        ),
        effective_chat=SimpleNamespace(id=789),
    )

    import asyncio

    asyncio.run(
        service.notify_manual_usage(
            update,
            action="Requested Today's Halal Menu",
            now=datetime(2026, 4, 15, 19, 30, tzinfo=ZoneInfo("America/Denver")),
        )
    )

    assert fake_bot.messages == [
        {
            "chat_id": 999,
            "text": (
                "This user used the bot:\n"
                "- Name: Akbar Khadjaev\n"
                "- Username: @a_khadjaev\n"
                "- User ID: 456\n"
                "- Chat ID: 789\n"
                "- Time: April 15, 2026 07:30 PM MDT\n"
                "- Action: Requested Today's Halal Menu"
            ),
        }
    ]
