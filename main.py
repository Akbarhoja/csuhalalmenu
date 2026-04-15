from __future__ import annotations

import logging

from bot import build_application
from config import load_settings
from db import DatabaseManager
from logging_config import configure_logging
from menu_service import MenuService
from nutrislice_client import NutrisliceClient
from stats_service import StatsService

LOGGER = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    settings = load_settings()

    LOGGER.info(
        "Starting CSU halal menu bot. Schedule=%02d:%02d Timezone=%s ChatID=%s Webhook=%s",
        settings.daily_send_hour,
        settings.daily_send_minute,
        settings.timezone_name,
        settings.telegram_chat_id,
        settings.use_webhook,
    )

    database = DatabaseManager(settings.database_url)
    stats_service = StatsService(database)
    stats_service.init_schema()

    menu_service = MenuService(NutrisliceClient(), settings.timezone_name)
    application = build_application(settings, menu_service, stats_service)
    if settings.use_webhook:
        if not settings.webhook_base_url:
            raise ValueError(
                "Webhook mode requires WEBHOOK_BASE_URL or RENDER_EXTERNAL_URL to be set."
            )

        application.run_webhook(
            listen="0.0.0.0",
            port=settings.port,
            url_path="telegram-webhook",
            webhook_url=f"{settings.webhook_base_url.rstrip('/')}/telegram-webhook",
            drop_pending_updates=True,
        )
        return

    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
