from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from models import KosherBistroMealMainFood
from utils import deduplicate_preserve_order, normalize_whitespace

PROTEIN_KEYWORDS = (
    "chicken",
    "beef",
    "lamb",
    "turkey",
    "salmon",
    "fish",
    "gyro",
    "shawarma",
    "kebab",
    "kofta",
)

ENTREE_STYLE_KEYWORDS = (
    "burger",
    "sandwich",
    "wrap",
    "pita",
    "bowl",
    "plate",
    "pasta",
    "curry",
    "stew",
    "grilled",
    "roasted",
    "baked",
)

SIDE_KEYWORDS = (
    "rice",
    "fries",
    "chips",
    "soup",
    "salad",
    "bread",
    "pita chips",
    "sauce",
    "hummus",
    "cookie",
    "brownie",
    "dessert",
    "drink",
    "beverage",
    "fruit",
    "yogurt",
)


class KosherBistroService:
    def extract_items(self, *, payload: Any, target_date: date) -> list[str]:
        relevant_payload = self._filter_payload_to_date(payload, target_date)
        if not isinstance(relevant_payload, dict):
            return []

        days = relevant_payload.get("days")
        if not isinstance(days, list):
            return []

        collected: list[str] = []
        for day in days:
            if not isinstance(day, dict):
                continue

            kosher_menu_ids = self._extract_kosher_bistro_menu_ids(day)
            if not kosher_menu_ids:
                continue

            for item in day.get("menu_items", []):
                if not isinstance(item, dict):
                    continue
                if item.get("is_station_header"):
                    continue

                menu_id = str(item.get("menu_id", ""))
                if menu_id not in kosher_menu_ids:
                    continue

                item_name = self._extract_item_name(item)
                if item_name:
                    collected.append(item_name)

        return deduplicate_preserve_order(collected)

    def choose_main_food(self, items: list[str]) -> KosherBistroMealMainFood:
        if not items:
            return KosherBistroMealMainFood(status="not_found")

        scored_items = [(item, self._score_item(item)) for item in items]
        ranked_items = sorted(scored_items, key=lambda pair: pair[1], reverse=True)
        best_item, best_score = ranked_items[0]
        second_score = ranked_items[1][1] if len(ranked_items) > 1 else float("-inf")

        if self._is_confident_choice(best_score=best_score, second_score=second_score):
            return KosherBistroMealMainFood(status="found", item_name=best_item)

        return KosherBistroMealMainFood(status="unclear", all_items=items)

    def _extract_item_name(self, item_payload: dict[str, Any]) -> str | None:
        food = item_payload.get("food")
        if isinstance(food, dict):
            name = normalize_whitespace(food.get("name", ""))
            if name:
                return name

        text_name = normalize_whitespace(item_payload.get("text", ""))
        return text_name or None

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

    def _score_item(self, item_name: str) -> int:
        lowered = item_name.casefold()
        words = tuple(self._tokenize(lowered))

        protein_hits = sum(1 for keyword in PROTEIN_KEYWORDS if keyword in lowered)
        entree_hits = sum(1 for keyword in ENTREE_STYLE_KEYWORDS if keyword in lowered)
        side_hits = sum(1 for keyword in SIDE_KEYWORDS if keyword in lowered)

        score = 0
        score += protein_hits * 7
        score += entree_hits * 4
        score += side_hits * -6

        if len(words) >= 2:
            score += 1
        if len(words) >= 3:
            score += 1

        if protein_hits and entree_hits:
            score += 2

        if side_hits and not protein_hits and not entree_hits:
            score -= 2

        return score

    def _is_confident_choice(self, *, best_score: int, second_score: int) -> bool:
        if best_score < 6:
            return False
        if second_score == float("-inf"):
            return True
        return best_score - second_score >= 2 or best_score >= 10

    def _tokenize(self, lowered_name: str) -> Iterable[str]:
        for token in lowered_name.replace("/", " ").replace("-", " ").split():
            cleaned = token.strip("(),.")
            if cleaned:
                yield cleaned
