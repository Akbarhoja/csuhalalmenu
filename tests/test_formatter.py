from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from formatter import format_daily_menu, format_stats_report
from models import (
    DailyMenuResult,
    DailyMenuSnapshot,
    KosherBistroMainFoods,
    KosherBistroMealMainFood,
    MenuEntry,
    MessageStatsSummary,
)
from stats_service import StatsReport


def test_format_daily_menu_with_results() -> None:
    snapshot = DailyMenuSnapshot(
        target_date="2026-04-10",
        fetched_at=datetime(2026, 4, 10, 7, 0, tzinfo=ZoneInfo("America/Denver")),
        result=DailyMenuResult(
            by_meal={
                "Breakfast": {
                    "Braiden Hall": [
                        MenuEntry(location_name="Braiden Hall", item_name="Halal Chicken Sausage"),
                    ]
                },
                "Lunch": {
                    "Rams Horn": [
                        MenuEntry(location_name="Rams Horn", item_name="Halal Lamb Bowl"),
                    ]
                },
                "Dinner": {},
            }
        ),
        kosher_bistro_main_foods=KosherBistroMainFoods(
            lunch=KosherBistroMealMainFood(
                status="found",
                item_name="Chicken Tagine",
                calories=620.0,
            ),
            dinner=KosherBistroMealMainFood(
                status="found",
                item_name="Braised Brisket",
                calories=780.0,
            ),
        ),
    )

    message = format_daily_menu(snapshot, datetime(2026, 4, 10, tzinfo=ZoneInfo("America/Denver")))

    assert "Date: April 10, 2026" in message
    assert "Last update: April 10, 2026 07:00 AM MDT" in message
    assert "Breakfast:" in message
    assert "- Braiden Hall" in message
    assert "  - Halal Chicken Sausage" in message
    assert "Dinner:\n- No halal items found" in message
    assert message.endswith(
        "Kosher Bistro Main Foods:\n"
        "Lunch:\n"
        "- Chicken Tagine (620 cal)\n\n"
        "Dinner:\n"
        "- Braised Brisket (780 cal)"
    )


def test_format_daily_menu_without_results() -> None:
    snapshot = DailyMenuSnapshot(
        target_date="2026-04-10",
        fetched_at=datetime(2026, 4, 10, 7, 0, tzinfo=ZoneInfo("America/Denver")),
        result=DailyMenuResult(by_meal={"Breakfast": {}, "Lunch": {}, "Dinner": {}}),
        kosher_bistro_main_foods=KosherBistroMainFoods(
            lunch=KosherBistroMealMainFood(status="not_found"),
            dinner=KosherBistroMealMainFood(status="calories_unavailable"),
        ),
    )

    message = format_daily_menu(snapshot, datetime(2026, 4, 10, tzinfo=ZoneInfo("America/Denver")))

    assert message.endswith(
        "Kosher Bistro Main Foods:\n"
        "Lunch:\n"
        "- No Kosher Bistro items found for lunch\n\n"
        "Dinner:\n"
        "- Found Kosher Bistro items, but calorie data is unavailable"
    )


def test_format_stats_report() -> None:
    report = StatsReport(
        today=MessageStatsSummary(
            total_messages=17,
            successful=16,
            failed=1,
            unique_chats=9,
            scheduled=1,
            manual=16,
        ),
        all_time=MessageStatsSummary(
            total_messages=428,
            successful=420,
            failed=8,
            unique_chats=57,
            scheduled=20,
            manual=408,
        ),
    )

    message = format_stats_report(report, "April 15, 2026")

    assert message == (
        "Bot Stats\n\n"
        "Today (April 15, 2026):\n"
        "- Total messages: 17\n"
        "- Successful: 16\n"
        "- Failed: 1\n"
        "- Unique chats: 9\n"
        "- Scheduled: 1\n"
        "- Manual: 16\n\n"
        "All-time:\n"
        "- Total messages: 428\n"
        "- Successful: 420\n"
        "- Failed: 8\n"
        "- Unique chats: 57"
    )
