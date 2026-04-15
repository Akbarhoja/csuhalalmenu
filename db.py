from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    case,
    create_engine,
    func,
    insert,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from models import MessageLogEntry, MessageStatsSummary

LOGGER = logging.getLogger(__name__)

METADATA = MetaData()

MESSAGE_LOGS = Table(
    "message_logs",
    METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_date", Date, nullable=False, index=True),
    Column("chat_id", BigInteger, nullable=False, index=True),
    Column("message_type", String(64), nullable=False, index=True),
    Column("success", Boolean, nullable=False, index=True),
    Column("sent_at", DateTime(timezone=True), nullable=False, index=True),
    Column("failure_reason", Text, nullable=True),
)


class DatabaseManager:
    def __init__(self, database_url: str) -> None:
        self._database_url = self._normalize_database_url(database_url)
        connect_args: dict[str, Any] = {}
        if self._database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        self.engine: Engine = create_engine(
            self._database_url,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )

    def init_schema(self) -> None:
        try:
            METADATA.create_all(self.engine)
        except SQLAlchemyError:
            LOGGER.exception("Failed to initialize database schema.")
            raise

    def insert_message_log(self, entry: MessageLogEntry) -> None:
        statement = insert(MESSAGE_LOGS).values(
            event_date=entry.event_date,
            chat_id=entry.chat_id,
            message_type=entry.message_type,
            success=entry.success,
            sent_at=entry.sent_at,
            failure_reason=entry.failure_reason,
        )
        try:
            with self.engine.begin() as connection:
                connection.execute(statement)
        except SQLAlchemyError:
            LOGGER.exception("Failed to insert message log entry.")
            raise

    def fetch_summary(self, *, event_date: date | None = None) -> MessageStatsSummary:
        filters = []
        if event_date is not None:
            filters.append(MESSAGE_LOGS.c.event_date == event_date)

        statement = select(
            func.count(MESSAGE_LOGS.c.id).label("total_messages"),
            func.coalesce(func.sum(case((MESSAGE_LOGS.c.success.is_(True), 1), else_=0)), 0).label("successful"),
            func.coalesce(func.sum(case((MESSAGE_LOGS.c.success.is_(False), 1), else_=0)), 0).label("failed"),
            func.count(func.distinct(MESSAGE_LOGS.c.chat_id)).label("unique_chats"),
            func.coalesce(
                func.sum(case((MESSAGE_LOGS.c.message_type == "scheduled_daily", 1), else_=0)),
                0,
            ).label("scheduled"),
            func.coalesce(
                func.sum(case((MESSAGE_LOGS.c.message_type == "manual_menu", 1), else_=0)),
                0,
            ).label("manual"),
        )
        if filters:
            statement = statement.where(*filters)

        try:
            with self.engine.begin() as connection:
                row = connection.execute(statement).one()
        except SQLAlchemyError:
            LOGGER.exception("Failed to fetch message stats summary.")
            raise

        return MessageStatsSummary(
            total_messages=int(row.total_messages or 0),
            successful=int(row.successful or 0),
            failed=int(row.failed or 0),
            unique_chats=int(row.unique_chats or 0),
            scheduled=int(row.scheduled or 0),
            manual=int(row.manual or 0),
        )

    def _normalize_database_url(self, database_url: str) -> str:
        if database_url.startswith("postgresql+"):
            return database_url
        if database_url.startswith("postgres://"):
            return "postgresql+psycopg://" + database_url[len("postgres://") :]
        if database_url.startswith("postgresql://"):
            return "postgresql+psycopg://" + database_url[len("postgresql://") :]
        return database_url
