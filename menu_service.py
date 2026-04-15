from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from constants import MEAL_ORDER
from models import (
    DailyMenuResult,
    DailyMenuSnapshot,
    DiningLocation,
    KosherBistroMainFood,
    MenuEntry,
)
from nutrislice_client import NutrisliceClient
from utils import deduplicate_preserve_order, normalize_whitespace

LOGGER = logging.getLogger(__name__)


class MenuService:
    def __init__(self, client: NutrisliceClient, timezone_name: str) -> None:
        self._client = client
        self._timezone_name = timezone_name
        self._cache_lock = asyncio.Lock()
        self._cached_snapshot: DailyMenuSnapshot | None = None

    async def get_today_halal_menu(self, now: datetime) -> DailyMenuSnapshot:
        target_date_text = now.date().isoformat()
        cached_snapshot = self._cached_snapshot
        if cached_snapshot is not None and cached_snapshot.target_date == target_date_text:
            LOGGER.info(
                "Using cached halal menu for %s fetched at %s.",
                cached_snapshot.target_date,
                cached_snapshot.fetched_at.isoformat(),
            )
            return cached_snapshot

        async with self._cache_lock:
            cached_snapshot = self._cached_snapshot
            if cached_snapshot is not None and cached_snapshot.target_date == target_date_text:
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
        kosher_bistro_candidates: list[dict[str, Any]] = []

        for location in locations:
            for meal_name in MEAL_ORDER:
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
                    continue

                entries = self._extract_halal_entries(
                    payload=payload,
                    location=location,
                    target_date=target_date,
                )
                if entries:
                    results[meal_name][location.name] = entries

                if self._is_foundry(location):
                    kosher_bistro_candidates.extend(
                        self._extract_kosher_bistro_items(payload=payload, target_date=target_date)
                    )

        return DailyMenuSnapshot(
            target_date=target_date.isoformat(),
            fetched_at=now,
            result=DailyMenuResult(by_meal=results),
            kosher_bistro_main_food=self._build_kosher_bistro_main_food(kosher_bistro_candidates),
        )

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

    def _extract_kosher_bistro_items(self, *, payload: Any, target_date: date) -> list[dict[str, Any]]:
        relevant_payload = self._filter_payload_to_date(payload, target_date)
        if not isinstance(relevant_payload, dict):
            return []

        days = relevant_payload.get("days")
        if not isinstance(days, list):
            return []

        collected: dict[str, dict[str, Any]] = {}
        for day in days:
            if not isinstance(day, dict):
                continue

            kosher_menu_ids = self._extract_kosher_bistro_menu_ids(day)
            if not kosher_menu_ids:
                continue

            for item in day.get("menu_items", []):
                if not isinstance(item, dict):
                    continue

                menu_id = str(item.get("menu_id", ""))
                if menu_id not in kosher_menu_ids:
                    continue
                if item.get("is_station_header"):
                    continue

                food = item.get("food")
                if not isinstance(food, dict):
                    continue

                item_name = normalize_whitespace(food.get("name", "") or item.get("text", ""))
                if not item_name:
                    continue

                calories = self._parse_calories(food)
                key = item_name.casefold()
                existing = collected.get(key)
                if existing is None or (
                    calories is not None and (
                        existing["calories"] is None or calories > existing["calories"]
                    )
                ):
                    collected[key] = {
                        "item_name": item_name,
                        "calories": calories,
                    }

        return list(collected.values())

    def _extract_kosher_bistro_menu_ids(self, day_payload: dict[str, Any]) -> set[str]:
        menu_info = day_payload.get("menu_info")
        if not isinstance(menu_info, dict):
            return set()

        kosher_menu_ids: set[str] = set()
        for menu_id, info in menu_info.items():
            if not isinstance(info, dict):
                continue

            section_options = info.get("section_options")
            if not isinstance(section_options, dict):
                continue

            display_name = normalize_whitespace(section_options.get("display_name", ""))
            display_name_cf = display_name.casefold()
            if "kosher" in display_name_cf and "bistro" in display_name_cf:
                kosher_menu_ids.add(str(menu_id))
        return kosher_menu_ids

    def _build_kosher_bistro_main_food(
        self,
        candidates: list[dict[str, Any]],
    ) -> KosherBistroMainFood:
        if not candidates:
            return KosherBistroMainFood(status="not_found")

        with_calories = [
            candidate
            for candidate in candidates
            if isinstance(candidate.get("calories"), (int, float))
        ]
        if not with_calories:
            return KosherBistroMainFood(status="calories_unavailable")

        best = max(with_calories, key=lambda candidate: candidate["calories"])
        return KosherBistroMainFood(
            status="found",
            item_name=best["item_name"],
            calories=float(best["calories"]),
        )

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

    def _parse_calories(self, food_payload: dict[str, Any]) -> float | None:
        rounded_nutrition_info = food_payload.get("rounded_nutrition_info")
        if isinstance(rounded_nutrition_info, dict):
            parsed = self._safe_float(rounded_nutrition_info.get("calories"))
            if parsed is not None:
                return parsed

        return self._safe_float(food_payload.get("calories"))

    def _safe_float(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace(",", "")
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

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
