from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
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
    port: int
    webhook_base_url: str | None
    use_webhook: bool
    database_url: str
    admin_chat_id: int
    admin_user_id: int | None


def load_settings() -> Settings:
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=env_path, override=True, encoding="utf-8-sig")

    token = _require_env("TELEGRAM_BOT_TOKEN")
    chat_id_raw = _require_env("TELEGRAM_CHAT_ID")
    database_url = _require_env("DATABASE_URL")
    daily_send_hour = _parse_bounded_int("DAILY_SEND_HOUR", default="7", minimum=0, maximum=23)
    daily_send_minute = _parse_bounded_int("DAILY_SEND_MINUTE", default="0", minimum=0, maximum=59)
    timezone_name = os.getenv("TIMEZONE", "America/Denver").strip() or "America/Denver"
    port = _parse_bounded_int("PORT", default="10000", minimum=1, maximum=65535)
    webhook_base_url = (
        os.getenv("WEBHOOK_BASE_URL", "").strip()
        or os.getenv("RENDER_EXTERNAL_URL", "").strip()
        or None
    )
    use_webhook = _parse_bool("USE_WEBHOOK", default=bool(webhook_base_url))

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

    admin_chat_id = _parse_optional_int("ADMIN_CHAT_ID") or chat_id
    admin_user_id = _parse_optional_int("ADMIN_USER_ID")

    return Settings(
        telegram_bot_token=token,
        telegram_chat_id=chat_id,
        daily_send_hour=daily_send_hour,
        daily_send_minute=daily_send_minute,
        timezone_name=timezone_name,
        timezone=timezone,
        port=port,
        webhook_base_url=webhook_base_url,
        use_webhook=use_webhook,
        database_url=database_url,
        admin_chat_id=admin_chat_id,
        admin_user_id=admin_user_id,
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


def _parse_bool(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean-like value such as true or false.")


def _parse_optional_int(name: str) -> int | None:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
