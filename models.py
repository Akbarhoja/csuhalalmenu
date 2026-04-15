from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DiningLocation:
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class MenuEntry:
    location_name: str
    item_name: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class KosherBistroMealMainFood:
    status: str
    item_name: str | None = None
    calories: float | None = None


@dataclass(frozen=True, slots=True)
class KosherBistroMainFoods:
    lunch: KosherBistroMealMainFood
    dinner: KosherBistroMealMainFood


@dataclass(slots=True)
class DailyMenuResult:
    by_meal: dict[str, dict[str, list[MenuEntry]]] = field(default_factory=dict)

    def has_any_items(self) -> bool:
        return any(
            items
            for locations in self.by_meal.values()
            for items in locations.values()
        )


@dataclass(frozen=True, slots=True)
class DailyMenuSnapshot:
    target_date: str
    fetched_at: datetime
    result: DailyMenuResult
    kosher_bistro_main_foods: KosherBistroMainFoods
