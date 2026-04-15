from __future__ import annotations

from kosher_bistro_service import KosherBistroService


def test_kosher_bistro_service_detects_strong_entree() -> None:
    service = KosherBistroService()

    result = service.choose_main_food(
        ["Rice Pilaf", "Grilled Salmon Plate", "Fresh Salad"]
    )

    assert result.status == "found"
    assert result.item_name == "Grilled Salmon Plate"


def test_kosher_bistro_service_deprioritizes_side_items() -> None:
    service = KosherBistroService()

    result = service.choose_main_food(
        ["Fries", "Chicken Wrap", "Fruit Cup"]
    )

    assert result.status == "found"
    assert result.item_name == "Chicken Wrap"


def test_kosher_bistro_service_falls_back_when_no_clear_main_exists() -> None:
    service = KosherBistroService()

    result = service.choose_main_food(
        ["Rice Pilaf", "Fresh Salad", "Pita Bread"]
    )

    assert result.status == "unclear"
    assert result.item_name is None
    assert result.all_items == ["Rice Pilaf", "Fresh Salad", "Pita Bread"]
