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
                                "food": {"name": "Rice Pilaf"},
                                "food_id": 6,
                            },
                            {
                                "is_station_header": False,
                                "menu_id": 149086,
                                "food": {"name": "Chicken Shawarma Bowl"},
                                "food_id": 7,
                            },
                            {
                                "is_station_header": False,
                                "menu_id": 149086,
                                "food": {"name": "Fresh Salad"},
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
                                "food": {"name": "Rice Pilaf"},
                                "food_id": 9,
                            },
                            {
                                "is_station_header": False,
                                "menu_id": 149087,
                                "food": {"name": "Fresh Salad"},
                                "food_id": 10,
                            },
                            {
                                "is_station_header": False,
                                "menu_id": 149087,
                                "food": {"name": "Pita Bread"},
                                "food_id": 11,
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
    service = MenuService(client, "America/Denver", cache_ttl_seconds=300)
    now = datetime(2026, 4, 10, 8, 0, tzinfo=ZoneInfo("America/Denver"))

    first_snapshot = asyncio.run(service.get_today_halal_menu(now))
    second_snapshot = asyncio.run(service.get_today_halal_menu(now))

    assert first_snapshot is second_snapshot
    assert client.discover_calls == 1
    assert client.fetch_calls == 9


def test_menu_service_refreshes_after_cache_ttl_expires() -> None:
    client = FakeNutrisliceClient()
    service = MenuService(client, "America/Denver", cache_ttl_seconds=60)

    first_now = datetime(2026, 4, 10, 8, 0, tzinfo=ZoneInfo("America/Denver"))
    second_now = datetime(2026, 4, 10, 8, 2, tzinfo=ZoneInfo("America/Denver"))

    first_snapshot = asyncio.run(service.get_today_halal_menu(first_now))
    second_snapshot = asyncio.run(service.get_today_halal_menu(second_now))

    assert first_snapshot is not second_snapshot
    assert client.discover_calls == 2
    assert client.fetch_calls == 18


def test_menu_service_prefers_strong_entree_over_side_items_for_lunch() -> None:
    client = FakeNutrisliceClient()
    service = MenuService(client, "America/Denver")

    snapshot = asyncio.run(
        service.get_today_halal_menu(
            datetime(2026, 4, 10, 8, 0, tzinfo=ZoneInfo("America/Denver"))
        )
    )

    lunch_main_food = snapshot.kosher_bistro_main_foods.lunch
    assert lunch_main_food.status == "found"
    assert lunch_main_food.item_name == "Chicken Shawarma Bowl"
    assert lunch_main_food.all_items == []


def test_menu_service_falls_back_to_all_items_when_main_is_unclear_for_dinner() -> None:
    client = FakeNutrisliceClient()
    service = MenuService(client, "America/Denver")

    snapshot = asyncio.run(
        service.get_today_halal_menu(
            datetime(2026, 4, 10, 8, 0, tzinfo=ZoneInfo("America/Denver"))
        )
    )

    dinner_main_food = snapshot.kosher_bistro_main_foods.dinner
    assert dinner_main_food.status == "unclear"
    assert dinner_main_food.item_name is None
    assert dinner_main_food.all_items == ["Rice Pilaf", "Fresh Salad", "Pita Bread"]
