from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from db import DatabaseManager
from models import MessageLogEntry, MessageStatsSummary

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StatsReport:
    today: MessageStatsSummary
    all_time: MessageStatsSummary


class StatsService:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def init_schema(self) -> None:
        self._database.init_schema()

    async def log_message_attempt(
        self,
        *,
        chat_id: int,
        message_type: str,
        success: bool,
        sent_at,
        event_date=None,
        failure_reason: str | None = None,
    ) -> None:
        entry = MessageLogEntry(
            event_date=event_date or sent_at.date(),
            chat_id=chat_id,
            message_type=message_type,
            success=success,
            sent_at=sent_at,
            failure_reason=failure_reason[:1000] if failure_reason else None,
        )
        try:
            await asyncio.to_thread(self._database.insert_message_log, entry)
        except Exception:
            LOGGER.exception("Failed to persist message log entry.")

    async def build_report(self, today_date) -> StatsReport:
        today_summary = await asyncio.to_thread(self._database.fetch_summary, event_date=today_date)
        all_time_summary = await asyncio.to_thread(self._database.fetch_summary, event_date=None)
        return StatsReport(today=today_summary, all_time=all_time_summary)
