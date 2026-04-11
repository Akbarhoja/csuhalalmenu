from __future__ import annotations

import logging

from bot import build_application
from config import load_settings
from logging_config import configure_logging
from menu_service import MenuService
from nutrislice_client import NutrisliceClient

LOGGER = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    settings = load_settings()

    LOGGER.info(
        "Starting CSU halal menu bot. Schedule=%02d:%02d Timezone=%s ChatID=%s",
        settings.daily_send_hour,
        settings.daily_send_minute,
        settings.timezone_name,
        settings.telegram_chat_id,
    )

    menu_service = MenuService(NutrisliceClient(), settings.timezone_name)
    application = build_application(settings, menu_service)
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
