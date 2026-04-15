from __future__ import annotations

import asyncio
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from db import DatabaseManager
from stats_service import StatsService


def test_stats_service_logs_and_aggregates_message_stats() -> None:
    with TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / 'stats.db'
        database = DatabaseManager(f"sqlite+pysqlite:///{db_path.as_posix()}")
        service = StatsService(database)
        service.init_schema()

        sent_at = datetime(2026, 4, 15, 9, 30, tzinfo=ZoneInfo('America/Denver'))

        asyncio.run(
            service.log_message_attempt(
                chat_id=1001,
                message_type='manual_menu',
                success=True,
                sent_at=sent_at,
            )
        )
        asyncio.run(
            service.log_message_attempt(
                chat_id=1001,
                message_type='manual_menu',
                success=False,
                sent_at=sent_at,
                failure_reason='telegram timeout',
            )
        )
        asyncio.run(
            service.log_message_attempt(
                chat_id=1002,
                message_type='scheduled_daily',
                success=True,
                sent_at=sent_at,
            )
        )

        report = asyncio.run(service.build_report(date(2026, 4, 15)))

        assert report.today.total_messages == 3
        assert report.today.successful == 2
        assert report.today.failed == 1
        assert report.today.unique_chats == 2
        assert report.today.scheduled == 1
        assert report.today.manual == 2

        assert report.all_time.total_messages == 3
        assert report.all_time.successful == 2
        assert report.all_time.failed == 1
        assert report.all_time.unique_chats == 2
