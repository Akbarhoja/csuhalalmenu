from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from formatter import format_daily_menu
from models import (
    DailyMenuResult,
    DailyMenuSnapshot,
    KosherBistroMainFoods,
    KosherBistroMealMainFood,
    MenuEntry,
)


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
