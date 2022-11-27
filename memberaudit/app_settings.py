import unidecode

from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from app_utils.django import clean_setting

MEMBERAUDIT_APP_NAME = clean_setting(
    "MEMBERAUDIT_APP_NAME", _("Member Audit"), required_type=str
)
"""Name of this app as shown in the Auth sidebar and page titles."""

MEMBERAUDIT_BASE_URL = slugify(
    unidecode.unidecode(MEMBERAUDIT_APP_NAME), allow_unicode=True
)


MEMBERAUDIT_BULK_METHODS_BATCH_SIZE = clean_setting(
    "MEMBERAUDIT_BULK_METHODS_BATCH_SIZE", 500
)
"""Technical parameter defining the maximum number of objects processed per run
of Django batch methods, e.g. bulk_create and bulk_update.
"""

# Activate developer mode for additional debug output. Undocumented feature
MEMBERAUDIT_DEVELOPER_MODE = clean_setting("MEMBERAUDIT_DEVELOPER_MODE", False)


MEMBERAUDIT_ESI_ERROR_LIMIT_THRESHOLD = clean_setting(
    "MEMBERAUDIT_ESI_ERROR_LIMIT_THRESHOLD", 25
)
"""ESI error limit remain threshold. The number of remaining errors is counted down
from 100 as errors occur. Because multiple tasks may request the value simultaneously
and get the same response, the threshold must be above 0
to prevent the API from shutting down with a 420 error.
"""


MEMBERAUDIT_LOCATION_STALE_HOURS = clean_setting("MEMBERAUDIT_LOCATION_STALE_HOURS", 24)
"""Hours after a existing location (e.g. structure) becomes stale and gets updated
e.g. for name changes of structures.
"""

MEMBERAUDIT_DATA_EXPORT_MIN_UPDATE_AGE = clean_setting(
    "MEMBERAUDIT_DATA_EXPORT_MIN_UPDATE_AGE", 60
)
"""Minimum age of existing export file before next update can be started in minutes."""


MEMBERAUDIT_LOG_UPDATE_STATS = clean_setting("MEMBERAUDIT_LOG_UPDATE_STATS", False)
"""When set True will log the update stats at the start of every run
The update stats include the measures durations from the last run per round and section.
"""

MEMBERAUDIT_MAX_MAILS = clean_setting("MEMBERAUDIT_MAX_MAILS", 250)
"""Maximum amount of mails fetched from ESI for each character."""


MEMBERAUDIT_TASKS_MAX_ASSETS_PER_PASS = clean_setting(
    "MEMBERAUDIT_TASKS_MAX_ASSETS_PER_PASS", 2500
)
"""Technical parameter defining the maximum number of asset items processed in each pass
when updating character assets.
A higher value reduces duration, but also increases task queue congestion.
"""

MEMBERAUDIT_TASKS_TIME_LIMIT = clean_setting("MEMBERAUDIT_TASKS_TIME_LIMIT", 7200)
"""Global timeout for tasks in seconds to reduce task accumulation during outages."""


MEMBERAUDIT_UPDATE_STALE_RING_1 = clean_setting("MEMBERAUDIT_UPDATE_STALE_RING_1", 60)
"""Character sections are updated on different schedules, called rings.
Ring 1 is the quickest, Ring 3 is the slowest
Settings define after how many minutes a section is considered stale.

Minutes after which sections belonging to ring 1 are considered stale:
location, online status
"""

MEMBERAUDIT_UPDATE_STALE_RING_2 = clean_setting("MEMBERAUDIT_UPDATE_STALE_RING_2", 240)
"""Minutes after which sections belonging to ring 2 are considered stale,
all except those in ring 1 & 3.
"""

MEMBERAUDIT_UPDATE_STALE_RING_3 = clean_setting("MEMBERAUDIT_UPDATE_STALE_RING_3", 480)
"""Minutes after which sections belonging to ring 3 are considered stale, assets."""


MEMBERAUDIT_UPDATE_STALE_OFFSET = clean_setting("MEMBERAUDIT_UPDATE_STALE_OFFSET", 5)
"""Actual value for considering staleness of a ring will be the above value
minus this offset. Required to avoid time synchronization issues.
"""

MEMBERAUDIT_DATA_RETENTION_LIMIT = clean_setting(
    "MEMBERAUDIT_DATA_RETENTION_LIMIT", default_value=360, min_value=7
)
"""Maximum number of days to keep historical data for mails, contracts and wallets.
Minimum is 7 day.
"""

####################
# Internal settings

# Timeout for caching objects when running tasks in seconds
MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT = clean_setting(
    "MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT", 600
)
