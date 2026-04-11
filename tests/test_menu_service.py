from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from menu_service import MenuService
from models import DiningLocation


class FakeNutrisliceClient:
    def __init__(self) -> None:
        self.discover_calls = 0
        self.fetch_calls = 0

    async def discover_locations(self) -> list[DiningLocation]:
        self.discover_calls += 1
        return [
            DiningLocation(name="Braiden Hall", slug="braiden-hall"),
            DiningLocation(name="Rams Horn", slug="rams-horn"),
        ]

    async def fetch_menu_payload(self, *, location_slug: str, meal_name: str, target_date: Any) -> Any:
        del target_date
        self.fetch_calls += 1
        payloads = {
            ("braiden-hall", "Breakfast"): {
                "menu_items": [
                    {"name": "Halal Chicken Sausage", "food_id": 1},
                    {"name": "Scrambled Eggs", "food_id": 2},
                    {"food": {"name": "HALAL Chicken Sausage"}, "food_id": 3},
                ]
            },
            ("braiden-hall", "Lunch"): {"menu_items": []},
            ("braiden-hall", "Dinner"): {"menu_items": []},
            ("rams-horn", "Breakfast"): {"menu_items": []},
            ("rams-horn", "Lunch"): {
                "sections": [
                    {
                        "items": [
                            {"food": {"name": "Rice Bowl", "description": "served with halal beef"}, "food_id": 4},
                            {"food": {"name": "Salad Bowl", "description": "fresh greens"}, "food_id": 5},
                        ]
                    }
                ]
            },
            ("rams-horn", "Dinner"): {"menu_items": []},
        }
        return payloads[(location_slug, meal_name)]


def test_menu_service_filters_halal_and_deduplicates() -> None:
    client = FakeNutrisliceClient()
    service = MenuService(client, "America/Denver")

    snapshot = asyncio.run(
        service.get_today_halal_menu(
            datetime(2026, 4, 10, 8, 0, tzinfo=ZoneInfo("America/Denver"))
        )
    )

    result = snapshot.result
    assert snapshot.target_date == "2026-04-10"
    assert list(result.by_meal["Breakfast"].keys()) == ["Braiden Hall"]
    assert [entry.item_name for entry in result.by_meal["Breakfast"]["Braiden Hall"]] == [
        "Halal Chicken Sausage"
    ]
    assert list(result.by_meal["Lunch"].keys()) == ["Rams Horn"]
    assert [entry.item_name for entry in result.by_meal["Lunch"]["Rams Horn"]] == [
        "Rice Bowl"
    ]
    assert result.by_meal["Dinner"] == {}


def test_menu_service_uses_same_day_cache() -> None:
    client = FakeNutrisliceClient()
    service = MenuService(client, "America/Denver")
    now = datetime(2026, 4, 10, 8, 0, tzinfo=ZoneInfo("America/Denver"))

    first_snapshot = asyncio.run(service.get_today_halal_menu(now))
    second_snapshot = asyncio.run(service.get_today_halal_menu(now))

    assert first_snapshot is second_snapshot
    assert client.discover_calls == 1
    assert client.fetch_calls == 6
