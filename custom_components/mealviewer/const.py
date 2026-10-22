"""Constants for the MealViewer integration."""

from datetime import timedelta
import logging

DOMAIN = "mealviewer"
LOGGER = logging.getLogger(__package__)

CONF_SCHOOL = "school"
CONF_DAYS_AHEAD = "days_ahead"
CONF_ROLLOVER_TIME = "rollover_time"
CONF_MEAL_TIMES = "meal_times"
CONF_START = "start"
CONF_END = "end"

DEFAULT_DAYS_AHEAD = 14
DEFAULT_ROLLOVER_TIME = "12:00:00"

UPDATE_INTERVAL = timedelta(hours=6)

ENTREE_CATEGORY = "ENTREES"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"
ATTR_BLOCKS = "blocks"
ATTR_CATEGORIES = "categories"
