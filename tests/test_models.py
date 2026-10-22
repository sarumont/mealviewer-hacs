"""Tests for MealViewer models."""

from datetime import date

from custom_components.mealviewer.api import parse_school_lookup
from custom_components.mealviewer.models import Menu, as_dict

THU = date(2026, 10, 22)
SAT = date(2026, 10, 24)
MON = date(2026, 10, 26)


def test_parse_menu(menu_payload) -> None:
    """Payload parses into the full structure."""
    menu = Menu.from_dict(menu_payload)

    assert menu.school.id == 9003
    assert menu.school.lookup == "AppletonElementarySchool"
    assert menu.school.url.endswith("/school/AppletonElementarySchool")
    assert menu.school.logo_url == (
        "https://appassets.mealviewer.com/schoollogo/619/9003/JY-lMPqZH0OiIkCP1rb0nw.png"
    )
    assert menu.block_names == {"breakfast": "Breakfast", "lunch": "Lunch"}
    assert {p["name"] for p in menu.info.prices} >= {"Adult Lunch"}
    assert "Gluten" in menu.info.allergens

    assert menu.days[THU].is_school_day
    assert not menu.days[SAT].is_school_day
    assert menu.days[SAT].week_day_name == "Saturday"

    lunch = menu.days[THU].block("lunch")
    assert lunch is not None
    assert [i.display_name for i in lunch.items_in("ENTREES")] == [
        "Homestyle turkey & gravy",
        "Deli slider",
    ]
    turkey = lunch.items[0]
    assert turkey.category == "ENTREES"
    assert turkey.portion_unit == "1/2 CUP"
    assert turkey.image_url == (
        "https://appassets.mealviewer.com/fooditemimages/619/1ALSrqacrFO.jpg"
    )
    assert {a.name for a in turkey.allergens} == {"Gluten", "Milk (Leche)"}
    # Keyed by USDA nutrient code, not per-district id.
    assert turkey.nutrients["calories"].value == 201
    assert turkey.nutrients["calories"].unit == "kcal"
    assert turkey.nutrients["sodium"].unit == "mg"
    assert turkey.nutrients["protein"].name == "Protein"


def test_next_block_skips_weekend(menu_payload) -> None:
    """next_block finds the next served day."""
    menu = Menu.from_dict(menu_payload)
    assert menu.next_block("lunch", THU).date == THU
    assert menu.next_block("lunch", SAT).date == MON
    assert menu.next_block("supper", THU) is None


def test_as_dict_is_json_safe(menu_payload) -> None:
    """as_dict converts dates, including dict keys."""
    data = as_dict(Menu.from_dict(menu_payload))
    assert "2026-10-22" in data["days"]
    assert data["days"]["2026-10-22"]["blocks"][0]["date"] == "2026-10-22"


def test_parse_school_lookup() -> None:
    """IDs and URLs both work."""
    assert parse_school_lookup(" Foo ") == "Foo"
    assert parse_school_lookup("https://schools.mealviewer.com/school/Foo?x=1") == "Foo"
