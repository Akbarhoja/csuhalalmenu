from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: int
    daily_send_hour: int
    daily_send_minute: int
    timezone_name: str
    timezone: ZoneInfo


def load_settings() -> Settings:
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=env_path, override=True, encoding="utf-8-sig")

    token = _require_env("TELEGRAM_BOT_TOKEN")
    chat_id_raw = _require_env("TELEGRAM_CHAT_ID")
    daily_send_hour = _parse_bounded_int("DAILY_SEND_HOUR", default="7", minimum=0, maximum=23)
    daily_send_minute = _parse_bounded_int("DAILY_SEND_MINUTE", default="0", minimum=0, maximum=59)
    timezone_name = os.getenv("TIMEZONE", "America/Denver").strip() or "America/Denver"

    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Invalid TIMEZONE value: {timezone_name!r}. Use an IANA timezone like 'America/Denver'."
        ) from exc

    try:
        chat_id = int(chat_id_raw)
    except ValueError as exc:
        raise ValueError("TELEGRAM_CHAT_ID must be an integer.") from exc

    return Settings(
        telegram_bot_token=token,
        telegram_chat_id=chat_id,
        daily_send_hour=daily_send_hour,
        daily_send_minute=daily_send_minute,
        timezone_name=timezone_name,
        timezone=timezone,
    )


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(
            f"Missing required environment variable {name}. Copy .env.example to .env and fill it in."
        )
    return value


def _parse_bounded_int(name: str, *, default: str, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name, default).strip() or default
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc

    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return parsed
