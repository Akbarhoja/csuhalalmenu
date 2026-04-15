from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any

from constants import MEAL_ORDER
from kosher_bistro_service import KosherBistroService
from models import (
    DailyMenuResult,
    DailyMenuSnapshot,
    DiningLocation,
    KosherBistroMainFoods,
    MenuEntry,
)
from nutrislice_client import NutrisliceClient
from utils import deduplicate_preserve_order, normalize_whitespace

LOGGER = logging.getLogger(__name__)


class MenuService:
    def __init__(
        self,
        client: NutrisliceClient,
        timezone_name: str,
        *,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._client = client
        self._timezone_name = timezone_name
        self._kosher_bistro_service = KosherBistroService()
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache_lock = asyncio.Lock()
        self._cached_snapshot: DailyMenuSnapshot | None = None

    async def get_today_halal_menu(self, now: datetime) -> DailyMenuSnapshot:
        target_date_text = now.date().isoformat()
        cached_snapshot = self._cached_snapshot
        if self._is_cache_valid(cached_snapshot, now, target_date_text):
            LOGGER.info(
                "Using cached halal menu for %s fetched at %s.",
                cached_snapshot.target_date,
                cached_snapshot.fetched_at.isoformat(),
            )
            return cached_snapshot

        async with self._cache_lock:
            cached_snapshot = self._cached_snapshot
            if self._is_cache_valid(cached_snapshot, now, target_date_text):
                LOGGER.info(
                    "Using cached halal menu for %s fetched at %s.",
                    cached_snapshot.target_date,
                    cached_snapshot.fetched_at.isoformat(),
                )
                return cached_snapshot

            snapshot = await self._fetch_daily_snapshot(now)
            self._cached_snapshot = snapshot
            return snapshot

    async def refresh_today_halal_menu(self, now: datetime) -> DailyMenuSnapshot:
        async with self._cache_lock:
            snapshot = await self._fetch_daily_snapshot(now)
            self._cached_snapshot = snapshot
            return snapshot

    async def _fetch_daily_snapshot(self, now: datetime) -> DailyMenuSnapshot:
        target_date = now.date()
        locations = await self._client.discover_locations()
        LOGGER.info(
            "Checking halal items for %s across %s locations in %s.",
            target_date.isoformat(),
            len(locations),
            self._timezone_name,
        )

        results: dict[str, dict[str, list[MenuEntry]]] = {meal_name: {} for meal_name in MEAL_ORDER}
        kosher_items_by_meal: dict[str, list[str]] = {"Lunch": [], "Dinner": []}
        fetch_tasks = [
            self._fetch_meal_payload(
                location=location,
                meal_name=meal_name,
                target_date=target_date,
            )
            for location in locations
            for meal_name in MEAL_ORDER
        ]
        fetch_results = await asyncio.gather(*fetch_tasks)

        for location, meal_name, payload in fetch_results:
            if payload is None:
                continue

            entries = self._extract_halal_entries(
                payload=payload,
                location=location,
                target_date=target_date,
            )
            if entries:
                results[meal_name][location.name] = entries

            if self._is_foundry(location) and meal_name in kosher_items_by_meal:
                kosher_items_by_meal[meal_name].extend(
                    self._kosher_bistro_service.extract_items(payload=payload, target_date=target_date)
                )

        return DailyMenuSnapshot(
            target_date=target_date.isoformat(),
            fetched_at=now,
            result=DailyMenuResult(by_meal=results),
            kosher_bistro_main_foods=KosherBistroMainFoods(
                lunch=self._kosher_bistro_service.choose_main_food(kosher_items_by_meal["Lunch"]),
                dinner=self._kosher_bistro_service.choose_main_food(kosher_items_by_meal["Dinner"]),
            ),
        )

    async def _fetch_meal_payload(
        self,
        *,
        location: DiningLocation,
        meal_name: str,
        target_date: date,
    ) -> tuple[DiningLocation, str, Any | None]:
        try:
            payload = await self._client.fetch_menu_payload(
                location_slug=location.slug,
                meal_name=meal_name,
                target_date=target_date,
            )
        except Exception as exc:
            LOGGER.warning(
                "Failed to fetch %s menu for %s (%s): %s",
                meal_name,
                location.name,
                location.slug,
                exc,
            )
            return location, meal_name, None
        return location, meal_name, payload

    def _is_cache_valid(
        self,
        snapshot: DailyMenuSnapshot | None,
        now: datetime,
        target_date_text: str,
    ) -> bool:
        if snapshot is None or snapshot.target_date != target_date_text:
            return False
        return now - snapshot.fetched_at < self._cache_ttl

    def _extract_halal_entries(
        self,
        *,
        payload: Any,
        location: DiningLocation,
        target_date: date,
    ) -> list[MenuEntry]:
        matches: list[MenuEntry] = []
        relevant_payload = self._filter_payload_to_date(payload, target_date)
        for candidate in self._iter_menu_candidates(relevant_payload):
            name = normalize_whitespace(candidate.get("name", ""))
            description = normalize_whitespace(candidate.get("description", ""))
            haystack = f"{name} {description}".casefold()
            if "halal" not in haystack:
                continue
            if not name:
                continue
            matches.append(MenuEntry(location_name=location.name, item_name=name, description=description))

        unique_names = deduplicate_preserve_order(entry.item_name for entry in matches)
        deduplicated: list[MenuEntry] = []
        for unique_name in unique_names:
            for entry in matches:
                if entry.item_name.casefold() == unique_name.casefold():
                    deduplicated.append(entry)
                    break
        return deduplicated

    def _filter_payload_to_date(self, payload: Any, target_date: date) -> Any:
        if not isinstance(payload, dict):
            return payload

        days = payload.get("days")
        if not isinstance(days, list):
            return payload

        target_date_text = target_date.isoformat()
        matching_days = [
            day
            for day in days
            if isinstance(day, dict) and day.get("date") == target_date_text
        ]
        if not matching_days:
            return {"days": []}

        filtered_payload = dict(payload)
        filtered_payload["days"] = matching_days
        return filtered_payload

    def _iter_menu_candidates(self, payload: Any) -> Iterable[dict[str, str]]:
        if isinstance(payload, str):
            return []

        collected: list[dict[str, str]] = []
        for node in self._walk(payload):
            if not isinstance(node, dict):
                continue

            normalized = self._normalize_candidate(node)
            if normalized:
                collected.append(normalized)
        return collected

    def _normalize_candidate(self, node: dict[str, Any]) -> dict[str, str] | None:
        preferred_name_keys = ("name", "text", "label", "display_name", "item_name", "food_name", "title")
        preferred_description_keys = ("description", "desc", "short_description", "long_description")
        food_like_keys = (
            "food",
            "menu_item",
            "food_id",
            "ingredients",
            "food_category",
            "rounded_nutrition_info",
            "serving_size_info",
            "has_nutrition_info",
            "portion_size",
        )

        if "synced_name" in node and "custom_icon_url" in node:
            return None

        if not any(key in node for key in food_like_keys):
            return None

        name = self._first_text(node, preferred_name_keys)
        description = self._first_text(node, preferred_description_keys)

        food_node = node.get("food")
        if isinstance(food_node, dict):
            name = name or self._first_text(food_node, preferred_name_keys)
            description = description or self._first_text(food_node, preferred_description_keys)

        item_node = node.get("menu_item")
        if isinstance(item_node, dict):
            name = name or self._first_text(item_node, preferred_name_keys)
            description = description or self._first_text(item_node, preferred_description_keys)

        if not name and not description:
            return None
        return {
            "name": name or "",
            "description": description or "",
        }

    def _first_text(self, payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _is_foundry(self, location: DiningLocation) -> bool:
        location_name = normalize_whitespace(location.name).casefold()
        location_slug = location.slug.casefold()
        return "foundry" in location_name or "the-foundry" in location_slug

    def _walk(self, payload: Any) -> Iterable[Any]:
        yield payload
        if isinstance(payload, dict):
            for value in payload.values():
                yield from self._walk(value)
        elif isinstance(payload, list):
            for value in payload:
                yield from self._walk(value)
