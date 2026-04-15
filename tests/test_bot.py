from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from bot import todays_halal_menu
from config import Settings
from constants import GENERIC_ERROR_MESSAGE


class FailingMenuService:
    async def get_today_halal_menu(self, now: datetime):  # noqa: ANN202
        del now
        raise RuntimeError("fetch failed")


class FakeNotificationService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def notify_manual_usage(self, update, *, action: str, now: datetime) -> None:  # noqa: ANN001, ANN202
        self.calls.append({"update": update, "action": action, "now": now})


class FakeBot:
    def __init__(self) -> None:
        self.chat_actions: list[dict[str, object]] = []

    async def send_chat_action(self, *, chat_id: int, action: str) -> None:
        self.chat_actions.append({"chat_id": chat_id, "action": action})


class FakeMessage:
    def __init__(self) -> None:
        self.replies: list[dict[str, object]] = []

    async def reply_text(self, text: str, reply_markup=None) -> None:  # noqa: ANN001
        self.replies.append({"text": text, "reply_markup": reply_markup})


def test_todays_halal_menu_returns_error_on_first_try() -> None:
    fake_message = FakeMessage()
    fake_notification_service = FakeNotificationService()
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
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=456),
        effective_chat=SimpleNamespace(id=789),
        effective_message=fake_message,
    )
    context = SimpleNamespace(
        bot=fake_bot,
        application=SimpleNamespace(
            bot_data={
                "settings": settings,
                "menu_service": FailingMenuService(),
                "notification_service": fake_notification_service,
                "user_request_times": {},
            }
        ),
    )

    asyncio.run(todays_halal_menu(update, context))

    assert len(fake_message.replies) == 1
    assert fake_message.replies[0]["text"] == GENERIC_ERROR_MESSAGE
    assert len(fake_notification_service.calls) == 1
    assert fake_bot.chat_actions == [{"chat_id": 789, "action": "typing"}]
