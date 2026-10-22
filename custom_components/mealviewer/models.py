"""Data models for MealViewer API responses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
import re
from typing import Any

IMAGE_BASE_URL = "https://appassets.mealviewer.com/fooditemimages/"
SCHOOL_BASE_URL = "https://schools.mealviewer.com/school/"

# USDA nutrient codes are stable across districts; MealViewer's own nutrient
# ids are per-district, and which nutrients are present varies by school.
NUTRIENT_CODES: dict[int, str] = {
    208: "calories",
    203: "protein",
    204: "total_fat",
    205: "total_carbs",
    269: "sugars",
    539: "added_sugars",
    291: "fiber",
    307: "sodium",
    306: "potassium",
    601: "cholesterol",
    605: "trans_fat",
    606: "saturated_fat",
    301: "calcium",
    303: "iron",
    318: "vitamin_a_iu",
    320: "vitamin_a_rae",
    324: "vitamin_d",
    401: "vitamin_c",
}

_UNIT_RE = re.compile(r"\s*\(([^)]+)\)\s*$")


def slugify(value: str) -> str:
    """Lowercase snake_case slug."""
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _split_unit(name: str) -> tuple[str, str | None]:
    if match := _UNIT_RE.search(name):
        return name[: match.start()], match.group(1)
    if name.lower() == "calories":
        return name, "kcal"
    return name, None


def as_dict(obj: Any) -> Any:
    """Convert a model to JSON-safe primitives."""
    return _jsonable(asdict(obj))


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {_jsonable(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, date):
        return value.isoformat()
    return value


@dataclass(frozen=True, slots=True)
class Nutrient:
    """A nutrient value for one serving of a food item."""

    key: str
    code: int | None
    id: int
    name: str
    unit: str | None
    value: float | None
    raw_value: str | None
    valid: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Nutrient:
        name, unit = _split_unit(data["name"])
        code = data.get("nutrientCode")
        return cls(
            key=NUTRIENT_CODES.get(code) or slugify(name),
            code=code,
            id=data["id"],
            name=name,
            unit=unit,
            value=data.get("value"),
            raw_value=data.get("rawValue"),
            valid=bool(data.get("isValid")),
        )


@dataclass(frozen=True, slots=True)
class Allergen:
    """An allergen flagged on a food item."""

    id: int
    code: str | None
    name: str
    icon: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Allergen:
        return cls(
            id=data["id"],
            code=data.get("codeName"),
            name=data["name"],
            icon=data.get("svg"),
        )


@dataclass(frozen=True, slots=True)
class FoodItem:
    """A single item served on a cafeteria line."""

    id: int
    name: str
    display_name: str
    name_line_2: str | None
    category: str
    category_order: int
    order: int
    menu_name: str | None
    description: str | None
    ingredients: str | None
    portion_quantity: float | None
    portion_unit: str | None
    image_url: str | None
    price: float | None
    rating: int | None
    badges: list[Any]
    allergens: list[Allergen]
    nutrients: dict[str, Nutrient]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FoodItem:
        name = data["item_Name"].strip()
        lower = name.lower()
        image = data.get("imageFileName")
        nutrients = [Nutrient.from_dict(n) for n in data.get("nutritionals") or []]
        return cls(
            id=data["item_Id"],
            name=name,
            display_name=lower[:1].upper() + lower[1:],
            name_line_2=data.get("item_Name_Line_2") or None,
            category=data.get("item_Type") or "",
            category_order=data.get("item_Type_Order_Id") or 0,
            order=data.get("item_Order_Id") or 0,
            menu_name=data.get("menu_Name"),
            description=data.get("description") or None,
            ingredients=data.get("ingredients") or None,
            portion_quantity=data.get("portionQuantity"),
            portion_unit=data.get("portionUnit"),
            image_url=f"{IMAGE_BASE_URL}{image}" if image else None,
            price=data.get("price"),
            rating=data.get("item_RatingLevel"),
            badges=data.get("badges") or [],
            allergens=[Allergen.from_dict(a) for a in data.get("allergens") or []],
            nutrients={n.key: n for n in nutrients},
        )


@dataclass(frozen=True, slots=True)
class CafeteriaLine:
    """A serving line within a meal block."""

    id: int
    name: str
    items: list[FoodItem]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CafeteriaLine:
        return cls(
            id=data["id"],
            name=data["name"],
            items=[
                FoodItem.from_dict(i) for i in data["foodItemList"].get("data") or []
            ],
        )


@dataclass(frozen=True, slots=True)
class MealBlock:
    """A meal (Breakfast, Lunch, ...) served on a day."""

    id: int
    name: str
    slug: str
    date: date
    blacked_out: bool
    no_schedule_text: str | None
    order: int
    lines: list[CafeteriaLine]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MealBlock:
        return cls(
            id=data["id"],
            name=data["blockName"],
            slug=slugify(data["blockName"]),
            date=_date(data["scheduledDate"]),
            blacked_out=bool(data.get("blackedOut")),
            no_schedule_text=data.get("noScheduleText"),
            order=data.get("orderId") or 0,
            lines=[
                CafeteriaLine.from_dict(line)
                for line in data["cafeteriaLineList"].get("data") or []
            ],
        )

    @property
    def items(self) -> list[FoodItem]:
        """All items across all lines, in menu order."""
        return sorted(
            (item for line in self.lines for item in line.items),
            key=lambda i: (i.category_order, i.order),
        )

    def items_in(self, category: str) -> list[FoodItem]:
        """Items in one category (e.g. ENTREES)."""
        return [i for i in self.items if i.category == category]


@dataclass(frozen=True, slots=True)
class MenuDay:
    """All meal blocks for one date."""

    date: date
    week_day_name: str
    blocks: list[MealBlock]

    @property
    def is_school_day(self) -> bool:
        """True when any meal is scheduled."""
        return any(not b.blacked_out for b in self.blocks)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MenuDay:
        info = data["dateInformation"]
        return cls(
            date=_date(info["dateFull"]),
            week_day_name=info["weekDayName"],
            blocks=sorted(
                (MealBlock.from_dict(b) for b in data.get("menuBlocks") or []),
                key=lambda b: b.order,
            ),
        )

    def block(self, slug: str) -> MealBlock | None:
        """Block by slug, if served that day."""
        return next((b for b in self.blocks if b.slug == slug), None)


@dataclass(frozen=True, slots=True)
class School:
    """A MealViewer school (physicalLocation)."""

    id: int
    lookup: str
    name: str
    abbreviation: str | None
    address: str | None
    city: str | None
    state: str | None
    zip: str | None
    district_lookup: str | None
    color: str | None
    logo_file: str | None

    @property
    def url(self) -> str:
        """Public MealViewer page for the school."""
        return f"{SCHOOL_BASE_URL}{self.lookup}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> School:
        settings = data.get("schoolSettings") or {}
        return cls(
            id=data["id"],
            lookup=data["physicalLocationLookup"],
            name=data["name"],
            abbreviation=data.get("physicalLocationAbbreviation"),
            address=data.get("address"),
            city=data.get("city"),
            state=data.get("state"),
            zip=data.get("zip"),
            district_lookup=data.get("districtLookup"),
            color=settings.get("schoolColor"),
            logo_file=settings.get("schoolLogo"),
        )


@dataclass(frozen=True, slots=True)
class SchoolInfo:
    """School-level metadata returned alongside menus."""

    prices: list[dict[str, Any]]
    announcements: list[Any]
    disclaimers: list[dict[str, Any]]
    external_links: list[dict[str, Any]]
    features: list[dict[str, Any]]
    allergens: list[str]
    nutrients: list[dict[str, Any]]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SchoolInfo:
        return cls(
            prices=[
                {"name": p["name"], "price": p["price"], "order": p.get("order")}
                for p in data.get("schoolPriceInfo") or []
            ],
            announcements=data.get("announcements") or [],
            disclaimers=[
                {"title": d.get("title"), "content": d.get("content")}
                for d in data.get("disclaimers") or []
            ],
            external_links=[
                {
                    "text": link.get("linkText"),
                    "url": link.get("linkUrl"),
                    "emergency": bool(link.get("emergency")),
                }
                for link in data.get("externalLinks") or []
            ],
            features=[
                {
                    "name": f["name"],
                    "enabled": bool(f.get("enabled")),
                    "available": bool(f.get("available")),
                }
                for f in data.get("features") or []
            ],
            allergens=[a["name"] for a in data.get("physicalLocationAllergens") or []],
            nutrients=[
                {"key": n.key, "code": n.code, "name": n.name, "unit": n.unit}
                for n in (
                    Nutrient.from_dict(raw)
                    for raw in data.get("physicalLocationNutritionals") or []
                )
            ],
        )


@dataclass(frozen=True, slots=True)
class Menu:
    """A parsed MealViewer menu response for a date range."""

    school: School
    info: SchoolInfo
    days: dict[date, MenuDay] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Menu:
        days = (MenuDay.from_dict(d) for d in data.get("menuSchedules") or [])
        return cls(
            school=School.from_dict(data["physicalLocation"]),
            info=SchoolInfo.from_dict(data),
            days={d.date: d for d in days},
        )

    def next_block(self, slug: str, on_or_after: date) -> MealBlock | None:
        """First served (not blacked out) block on or after a date."""
        for day in sorted(self.days):
            if day < on_or_after:
                continue
            block = self.days[day].block(slug)
            if block and not block.blacked_out:
                return block
        return None

    @property
    def block_names(self) -> dict[str, str]:
        """slug -> name for every block seen in this range."""
        return {b.slug: b.name for day in self.days.values() for b in day.blocks}
