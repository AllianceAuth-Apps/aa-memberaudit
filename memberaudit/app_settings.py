"""Settings for Member Audit."""

from django.utils.translation import gettext_lazy as _

from app_utils.app_settings import clean_setting

MEMBERAUDIT_APP_NAME = clean_setting(
    "MEMBERAUDIT_APP_NAME", _("Member Audit"), required_type=str
)
"""Name of this app as shown in the Auth sidebar and page titles."""

MEMBERAUDIT_BULK_METHODS_BATCH_SIZE = clean_setting(
    "MEMBERAUDIT_BULK_METHODS_BATCH_SIZE", 500
)
"""Technical parameter defining the maximum number of objects processed per run
of Django batch methods, e.g. bulk_create and bulk_update.
"""

MEMBERAUDIT_DATA_RETENTION_LIMIT = clean_setting(
    "MEMBERAUDIT_DATA_RETENTION_LIMIT", default_value=360, min_value=7
)
"""Maximum number of days to keep historical data for mails, contracts and wallets.
Minimum is 7 day.
"""

MEMBERAUDIT_FEATURE_ROLES_ENABLED = clean_setting(
    "MEMBERAUDIT_FEATURE_ROLES_ENABLED", False
)
"""Feature flag to enable or disable the corporation roles feature."""

MEMBERAUDIT_DATA_EXPORT_MIN_UPDATE_AGE = clean_setting(
    "MEMBERAUDIT_DATA_EXPORT_MIN_UPDATE_AGE", 60
)
"""Minimum age of existing export file before next update can be started in minutes."""

MEMBERAUDIT_LOCATION_STALE_HOURS = clean_setting("MEMBERAUDIT_LOCATION_STALE_HOURS", 24)
"""Hours after a existing location (e.g. structure) becomes stale and gets updated
e.g. for name changes of structures.
"""

MEMBERAUDIT_MAX_MAILS = clean_setting("MEMBERAUDIT_MAX_MAILS", 250)
"""Maximum amount of mails fetched from ESI for each character."""

MEMBERAUDIT_NOTIFY_TOKEN_ERRORS = clean_setting("MEMBERAUDIT_NOTIFY_TOKEN_ERRORS", True)
"""When enabled will automatically notify users when their character has a token error.
But only once per character until the character is re-registered or this notification
is reset manually by admins.
"""

MEMBERAUDIT_SECTION_STALE_MINUTES_GLOBAL_DEFAULT = clean_setting(
    "MEMBERAUDIT_SECTION_STALE_MINUTES_GLOBAL_DEFAULT", 240
)
"""Default time in minutes after the last successful update at which a section
is considered stale and therefore needs to be updated.
All sections, which do not have a specific default value
and are not configured differently will use this value.

Tip: Please run the command ``memberaudit_stats`` to see the
currently effective configuration.
"""

MEMBERAUDIT_SECTION_STALE_MINUTES_CONFIG = clean_setting(
    "MEMBERAUDIT_SECTION_STALE_MINUTES_CONFIG", {}
)
"""Custom configuration of stale minutes for each section,
which will override the respective defaults.

Tip: Please run the command ``memberaudit_stats`` to see the
currently effective configuration.
"""

MEMBERAUDIT_SECTION_STALE_MINUTES_SECTION_DEFAULTS = {
    # former ring 1
    "location": 60,
    "online_status": 60,
    "ship": 60,
    "skill_queue": 60,
    # former ring 3
    "assets": 480,
    "attributes": 480,
    "corporation_history": 480,
    "fw_stats": 480,
    "loyalty": 480,
    "titles": 480,
}
"""Default values for stale minutes of specific sections.

:meta private:
"""

MEMBERAUDIT_STORE_ESI_DATA_ENABLED = clean_setting(
    "MEMBERAUDIT_STORE_ESI_DATA_ENABLED", False
)
"""Set to true to store incoming data from the ESI API to disk for debugging.

The data will be stored in JSON files under: `~/myauth/temp/memberaudit_log`.

Warning: Storing this data can quickly occupy a lot of disk space.
We strongly recommend to also define filters for sections and/or characters
to limit what data is stored.
"""

MEMBERAUDIT_STORE_ESI_DATA_SECTIONS = clean_setting(
    "MEMBERAUDIT_STORE_ESI_DATA_SECTIONS", []
)
"""List sections to filter storing debug data for. An empty list means all sections."""

MEMBERAUDIT_STORE_ESI_DATA_CHARACTERS = clean_setting(
    "MEMBERAUDIT_STORE_ESI_DATA_CHARACTERS", []
)
"""List character IDs to filter storing debug data for.
An empty list means all characters.
"""

MEMBERAUDIT_TASKS_HIGH_PRIORITY = clean_setting(
    "MEMBERAUDIT_TASKS_HIGH_PRIORITY", default_value=3, min_value=1, max_value=9
)
"""Priority for high priority tasks, e.g. user requests an action."""

MEMBERAUDIT_TASKS_MAX_ASSETS_PER_PASS = clean_setting(
    "MEMBERAUDIT_TASKS_MAX_ASSETS_PER_PASS", 2500
)
"""Technical parameter defining the maximum number of asset items processed in each pass
when updating character assets.
A higher value reduces duration, but also increases task queue congestion.
"""

MEMBERAUDIT_TASKS_LOW_PRIORITY = clean_setting(
    "MEMBERAUDIT_TASKS_LOW_PRIORITY", default_value=7, min_value=1, max_value=9
)
"""Priority for low priority tasks, e.g. updating characters."""

MEMBERAUDIT_TASKS_NORMAL_PRIORITY = clean_setting(
    "MEMBERAUDIT_TASKS_NORMAL_PRIORITY", default_value=5, min_value=1, max_value=9
)
"""Priority for normal tasks, e.g. updating characters."""

MEMBERAUDIT_TASKS_TIME_LIMIT = clean_setting("MEMBERAUDIT_TASKS_TIME_LIMIT", 7200)
"""Global timeout for tasks in seconds to reduce task accumulation during outages."""


####################
# Internal settings

# Timeout for caching objects when running tasks in seconds
MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT = clean_setting(
    "MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT", 600
)
