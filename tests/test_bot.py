from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from bot import menu_command, start_command, todays_halal_menu
from config import Settings
from constants import GENERIC_ERROR_MESSAGE, LOADING_MESSAGE, WELCOME_MESSAGE
from models import DailyMenuResult, DailyMenuSnapshot, KosherBistroMainFoods, KosherBistroMealMainFood


class SuccessfulMenuService:
    async def get_today_halal_menu(self, now: datetime) -> DailyMenuSnapshot:
        return DailyMenuSnapshot(
            target_date=now.date().isoformat(),
            fetched_at=now,
            result=DailyMenuResult(by_meal={"Breakfast": {}, "Lunch": {}, "Dinner": {}}),
            kosher_bistro_main_foods=KosherBistroMainFoods(
                lunch=KosherBistroMealMainFood(status="not_found"),
                dinner=KosherBistroMealMainFood(status="not_found"),
            ),
        )


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


class FakeSentMessage:
    def __init__(self, parent: "FakeMessage", text: str) -> None:
        self.parent = parent
        self.text = text
        self.edits: list[dict[str, object]] = []
        self.follow_ups: list[dict[str, object]] = []

    async def edit_text(self, text: str, reply_markup=None) -> None:  # noqa: ANN001
        self.text = text
        self.edits.append({"text": text, "reply_markup": reply_markup})

    async def reply_text(self, text: str, reply_markup=None):  # noqa: ANN001, ANN202
        self.follow_ups.append({"text": text, "reply_markup": reply_markup})
        return FakeSentMessage(self.parent, text)


class FakeMessage:
    def __init__(self) -> None:
        self.replies: list[dict[str, object]] = []
        self.sent_messages: list[FakeSentMessage] = []

    async def reply_text(self, text: str, reply_markup=None):  # noqa: ANN001, ANN202
        self.replies.append({"text": text, "reply_markup": reply_markup})
        sent = FakeSentMessage(self, text)
        self.sent_messages.append(sent)
        return sent


def _build_settings() -> Settings:
    return Settings(
        telegram_bot_token="token",
        timezone_name="America/Denver",
        timezone=ZoneInfo("America/Denver"),
        port=10000,
        webhook_base_url=None,
        use_webhook=False,
        admin_chat_id=999,
    )


def _build_context(menu_service) -> tuple[SimpleNamespace, SimpleNamespace, FakeMessage, FakeNotificationService, FakeBot]:
    fake_message = FakeMessage()
    fake_notification_service = FakeNotificationService()
    fake_bot = FakeBot()
    settings = _build_settings()
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
                "menu_service": menu_service,
                "notification_service": fake_notification_service,
                "user_request_times": {},
            }
        ),
    )
    return update, context, fake_message, fake_notification_service, fake_bot


def test_todays_halal_menu_shows_loading_then_final_response() -> None:
    update, context, fake_message, fake_notification_service, _ = _build_context(SuccessfulMenuService())

    asyncio.run(todays_halal_menu(update, context))

    assert fake_message.replies[0]["text"] == LOADING_MESSAGE
    assert fake_message.sent_messages[0].edits
    assert fake_message.sent_messages[0].edits[0]["text"].startswith("Meow")
    assert len(fake_notification_service.calls) == 1


def test_todays_halal_menu_returns_error_on_first_try() -> None:
    update, context, fake_message, fake_notification_service, fake_bot = _build_context(FailingMenuService())

    asyncio.run(todays_halal_menu(update, context))

    assert fake_message.replies[0]["text"] == LOADING_MESSAGE
    assert fake_message.sent_messages[0].edits[0]["text"] == GENERIC_ERROR_MESSAGE
    assert len(fake_notification_service.calls) == 1


def test_start_returns_welcome_message_and_keyboard() -> None:
    update, _, fake_message, _, fake_bot = _build_context(SuccessfulMenuService())
    context = SimpleNamespace(bot=fake_bot, application=SimpleNamespace(bot_data={}))

    asyncio.run(start_command(update, context))

    assert fake_message.replies[0]["text"] == WELCOME_MESSAGE
    assert fake_message.replies[0]["reply_markup"] is not None


def test_menu_command_triggers_same_flow_as_button() -> None:
    update, context, fake_message, fake_notification_service, _ = _build_context(SuccessfulMenuService())

    asyncio.run(menu_command(update, context))

    assert fake_message.replies[0]["text"] == LOADING_MESSAGE
    assert fake_message.sent_messages[0].edits
    assert len(fake_notification_service.calls) == 1
