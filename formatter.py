from __future__ import annotations

from datetime import datetime

from constants import INTRO_MESSAGE, MAX_TELEGRAM_MESSAGE_LENGTH, MEAL_ORDER, NO_ITEMS_MESSAGE
from models import DailyMenuSnapshot, KosherBistroMainFood


def format_daily_menu(snapshot: DailyMenuSnapshot, now: datetime) -> str:
    lines: list[str]
    result = snapshot.result

    if not result.has_any_items():
        lines = [
            NO_ITEMS_MESSAGE,
            "",
        ]
    else:
        lines = [
            INTRO_MESSAGE,
            "",
            f"Date: {now.strftime('%B %d, %Y')}",
            f"Last update: {snapshot.fetched_at.strftime('%B %d, %Y %I:%M %p %Z')}",
            "",
        ]

        for meal_name in MEAL_ORDER:
            lines.append(f"{meal_name}:")
            meal_locations = result.by_meal.get(meal_name, {})
            if not meal_locations:
                lines.append("- No halal items found")
                lines.append("")
                continue

            for location_name, entries in meal_locations.items():
                lines.append(f"- {location_name}")
                for entry in entries:
                    lines.append(f"  - {entry.item_name}")
            lines.append("")

    lines.extend(_format_kosher_bistro_section(snapshot.kosher_bistro_main_food))
    return "\n".join(lines).rstrip()


def _format_kosher_bistro_section(kosher_bistro_main_food: KosherBistroMainFood) -> list[str]:
    lines = [
        "Kosher Bistro Main Food:",
    ]

    if kosher_bistro_main_food.status == "found":
        calories_text = _format_calories(kosher_bistro_main_food.calories)
        lines.append(f"- {kosher_bistro_main_food.item_name} ({calories_text} cal)")
        return lines

    if kosher_bistro_main_food.status == "calories_unavailable":
        lines.append("- Found Kosher Bistro items, but calorie data is unavailable")
        return lines

    lines.append("- No Kosher Bistro items found today")
    return lines


def _format_calories(calories: float | None) -> str:
    if calories is None:
        return "0"
    if calories.is_integer():
        return str(int(calories))
    return f"{calories:g}"


def split_message(text: str, limit: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text

    while len(remaining) > limit:
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit

        chunk = remaining[:split_at].rstrip()
        if not chunk:
            chunk = remaining[:limit]
            split_at = limit

        chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()

    if remaining:
        chunks.append(remaining)

    return chunks
