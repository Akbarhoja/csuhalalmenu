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
        "Starting CSU halal menu bot. Timezone=%s AdminChatID=%s Webhook=%s",
        settings.timezone_name,
        settings.admin_chat_id,
        settings.use_webhook,
    )

    menu_service = MenuService(NutrisliceClient(), settings.timezone_name)
    application = build_application(settings, menu_service)
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
