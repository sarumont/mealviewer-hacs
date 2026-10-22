# Design

## API

`GET https://api.mealviewer.com/api/v4/school/{lookup}/{M-D-YYYY}/{M-D-YYYY}/0` (inclusive range,
no auth) returns menus plus school metadata, prices, allergen/nutrient catalogs, disclaimers, links,
announcements.

- Hierarchy: `menuSchedules[]` (day) → `menuBlocks[]` (meal) → `cafeteriaLineList.data[]` (line)
  → `foodItemList.data[]` (item).
- Block names are free-form per school, so entities are created per discovered block, and new
  blocks found on later refreshes get their own entities.
- No-school days: `menuBlocks: []`.
- Unknown school: HTTP 200 with `physicalLocation: null`. `GET /api/v4/physicalLocation/{lookup}`
  returns 404 instead and is used to validate in the config flow.
- Nutrient `id`s are per district; `nutrientCode` (USDA) is stable and is the key we use. The set of
  nutrients varies by school (e.g. total fat isn't always present).
- Item images: `https://appassets.mealviewer.com/fooditemimages/{imageFileName}`.
- School logos: `https://appassets.mealviewer.com/schoollogo/{schoolSettings.schoolLogo}` (same
  path in `physicalLocation` and `physicalLocation/search/{query}` results).

## Decisions

- **One config entry per school**, unique id = physicalLocation id (Mealie pattern).
- **Legacy flat item fields dropped** (`calories`, `g_T_Fat`, `milk`, `egg`, …): they're zeros or
  `false` even when `nutritionals`/`allergens` say otherwise. Diagnostics include the raw payload.
- **Calendar per meal block**; event title = entrees, description = full menu. Events are all-day
  unless the user sets serving times for that meal in options (MealViewer has no times).
- **Next-menu sensor per block** with structured attributes for dashboards; rolls over at a
  configurable time (default noon). `items` is unrecorded.
- **School-day binary sensor** for automations.
- **`get_menu` response service** is the "everything" interface (Mealie's `get_mealplan` pattern).
- The API client lives in the integration. HA core would require a separate PyPI library; HACS doesn't.
- Uses `probatio` schemas like current core, so HA 2026.10 is the minimum version.

## Refresh

The coordinator fetches today .. today+N (default 14) every 6h and at midnight. At rollover time,
listeners are updated without a fetch. Calendar/service ranges inside the cached window are served
from cache; others hit the API.

## Open

- Brand icon: submit to `home-assistant/brands` (the HACS validation ignores `brands` until then).
