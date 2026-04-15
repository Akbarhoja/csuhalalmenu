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
            DiningLocation(name="Ram's Horn Dining Center", slug="rams-horn"),
            DiningLocation(name="The Foundry", slug="the-foundry"),
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
            ("the-foundry", "Breakfast"): {"days": [{"date": "2026-04-10", "menu_info": {}, "menu_items": []}]},
            ("the-foundry", "Lunch"): {
                "days": [
                    {
                        "date": "2026-04-10",
                        "menu_info": {
                            "149086": {
                                "position": 6,
                                "section_options": {"display_name": "Kosher Bistro"},
                            }
                        },
                        "menu_items": [
                            {
                                "is_station_header": False,
                                "menu_id": 149086,
                                "food": {
                                    "name": "Chicken Tagine",
                                    "rounded_nutrition_info": {"calories": 620},
                                },
                                "food_id": 6,
                            },
                            {
                                "is_station_header": False,
                                "menu_id": 149086,
                                "food": {
                                    "name": "Falafel Plate",
                                    "rounded_nutrition_info": {"calories": "540"},
                                },
                                "food_id": 7,
                            },
                            {
                                "is_station_header": False,
                                "menu_id": 149086,
                                "food": {
                                    "name": "Mystery Lunch",
                                },
                                "food_id": 8,
                            },
                        ],
                    }
                ]
            },
            ("the-foundry", "Dinner"): {
                "days": [
                    {
                        "date": "2026-04-10",
                        "menu_info": {
                            "149087": {
                                "position": 6,
                                "section_options": {"display_name": "Kosher Bistro Dinner"},
                            }
                        },
                        "menu_items": [
                            {
                                "is_station_header": False,
                                "menu_id": 149087,
                                "food": {
                                    "name": "Braised Brisket",
                                    "rounded_nutrition_info": {"calories": 780},
                                },
                                "food_id": 9,
                            },
                            {
                                "is_station_header": False,
                                "menu_id": 149087,
                                "food": {
                                    "name": "Roasted Chicken",
                                    "rounded_nutrition_info": {"calories": 700},
                                },
                                "food_id": 10,
                            },
                        ],
                    }
                ]
            },
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
    assert list(result.by_meal["Lunch"].keys()) == ["Ram's Horn Dining Center"]
    assert [entry.item_name for entry in result.by_meal["Lunch"]["Ram's Horn Dining Center"]] == [
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
    assert client.fetch_calls == 9


def test_menu_service_selects_highest_calorie_kosher_bistro_lunch_item() -> None:
    client = FakeNutrisliceClient()
    service = MenuService(client, "America/Denver")

    snapshot = asyncio.run(
        service.get_today_halal_menu(
            datetime(2026, 4, 10, 8, 0, tzinfo=ZoneInfo("America/Denver"))
        )
    )

    lunch_main_food = snapshot.kosher_bistro_main_foods.lunch
    assert lunch_main_food.status == "found"
    assert lunch_main_food.item_name == "Chicken Tagine"
    assert lunch_main_food.calories == 620.0


def test_menu_service_selects_highest_calorie_kosher_bistro_dinner_item() -> None:
    client = FakeNutrisliceClient()
    service = MenuService(client, "America/Denver")

    snapshot = asyncio.run(
        service.get_today_halal_menu(
            datetime(2026, 4, 10, 8, 0, tzinfo=ZoneInfo("America/Denver"))
        )
    )

    dinner_main_food = snapshot.kosher_bistro_main_foods.dinner
    assert dinner_main_food.status == "found"
    assert dinner_main_food.item_name == "Braised Brisket"
    assert dinner_main_food.calories == 780.0
