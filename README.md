# MealViewer for Home Assistant

HACS integration for school breakfast and lunch menus from [MealViewer](https://schools.mealviewer.com).

## Install

1. HACS → ⋮ → Custom repositories → add `https://github.com/sarumont/mealviewer-hacs` as **Integration**.
2. Install **MealViewer**, restart Home Assistant.
3. Settings → Devices & services → Add integration → **MealViewer**.
4. Enter the school ID or paste its page URL, e.g.
   `https://schools.mealviewer.com/school/AppletonElementarySchool`.

Add one entry per school. Requires Home Assistant 2026.10 or newer.

## Entities

Per school (one device), per meal block the school serves (Breakfast, Lunch, …):

| Entity | State | Notes |
| --- | --- | --- |
| `calendar.<school>_<meal>` | current/next menu | All-day events. Title = entrees; description = full menu by category with macros and allergens. |
| `sensor.<school>_next_<meal>` | entrees, comma-separated | Today's menu, or the next school day's after the rollover time. Attributes: `date`, `block`, `entrees`, `items` (full structured items). |
| `binary_sensor.<school>_school_day` | on/off | On when any meal is served today. |

`items` is excluded from the recorder (too large for history).

## Options

- **Days ahead** (default 14): menu window fetched and cached.
- **Rollover time** (default 12:00): when next-menu sensors switch to the next school day.

Menus refresh every 6 hours and at midnight.

## Service: `mealviewer.get_menu`

Returns everything MealViewer publishes for a date range: school details, prices, announcements,
disclaimers, links, and for every item its category, portion, image URL, allergens and all nutrients.

```yaml
action: mealviewer.get_menu
data:
  config_entry_id: <entry id>
  start_date: "2026-10-26"
  end_date: "2026-10-30"
  blocks: [Lunch]          # optional
  categories: [ENTREES]    # optional: ENTREES, SIDES, FRUIT, MILK, ...
response_variable: menu
```

Nutrients are keyed by USDA nutrient code (`calories`, `protein`, `total_carbs`, `total_fat`,
`sugars`, `added_sugars`, `fiber`, `sodium`, `saturated_fat`, …). Which nutrients appear depends on
the school.

## Example: markdown card

```yaml
type: markdown
content: >
  {% set s = 'sensor.appleton_elementary_school_next_lunch' %}
  ### Lunch — {{ state_attr(s, 'date') }}
  {% for i in state_attr(s, 'items') if i.category == 'ENTREES' %}
  - {{ i.display_name }} ({{ i.nutrients.get('calories', {}).get('value', '?') }} Cal)
  {% endfor %}
```

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```
