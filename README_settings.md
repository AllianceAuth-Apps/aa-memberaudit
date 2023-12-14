# Settings

Name|Description|Default
--|--|--
`MEMBERAUDIT_APP_NAME`|Name of this app as shown in the Auth sidebar and page titles.|`Member Audit`
`MEMBERAUDIT_BULK_METHODS_BATCH_SIZE`|Technical parameter defining the maximum number of objects processed per run of Django batch methods, e.g. bulk_create and bulk_update.|`500`
`MEMBERAUDIT_DATA_EXPORT_MIN_UPDATE_AGE`|Minimum age of existing export file before next update can be started in minutes.|`60`
`MEMBERAUDIT_DATA_RETENTION_LIMIT`|Maximum number of days to keep historical data for mails, contracts and wallets. Minimum is 7 day.|`360`
`MEMBERAUDIT_FEATURE_ROLES_ENABLED`|Feature flag to enable or disable the corporation roles feature.|`False`
`MEMBERAUDIT_LOCATION_STALE_HOURS`|Hours after a existing location (e.g. structure) becomes stale and gets updated e.g. for name changes of structures.|`24`
`MEMBERAUDIT_MAX_MAILS`|Maximum amount of mails fetched from ESI for each character.|`250`
`MEMBERAUDIT_NOTIFY_TOKEN_ERRORS`|When enabled will automatically notify users when their character has a token error. But only once per character until the character is re-registered or this notification is reset manually by admins.|`True`
`MEMBERAUDIT_SECTION_STALE_MINUTES_CONFIG`|Custom configuration of stale minutes for each section, which will override the respective defaults.  Tip: Please run the command ``memberaudit_stats`` to see the currently effective configuration.|`{}`
`MEMBERAUDIT_SECTION_STALE_MINUTES_GLOBAL_DEFAULT`|Default time in minutes after the last successful update at which a section is considered stale and therefore needs to be updated. All sections, which do not have a specific default value and are not configured differently will use this value.  Tip: Please run the command ``memberaudit_stats`` to see the currently effective configuration.|`240`
`MEMBERAUDIT_STORE_ESI_DATA_CHARACTERS`|List character IDs to filter storing debug data for. An empty list means all characters.|`[]`
`MEMBERAUDIT_STORE_ESI_DATA_ENABLED`|Set to true to store incoming data from the ESI API to disk for debugging.  The data will be stored in JSON files under: `~/myauth/temp/memberaudit_log`.  Warning: Storing this data can quickly occupy a lot of disk space. We strongly recommend to also define filters for sections and/or characters to limit what data is stored.|`False`
`MEMBERAUDIT_STORE_ESI_DATA_SECTIONS`|List sections to filter storing debug data for. An empty list means all sections.|`[]`
`MEMBERAUDIT_TASKS_HIGH_PRIORITY`|Priority for high priority tasks, e.g. user requests an action.|`3`
`MEMBERAUDIT_TASKS_LOW_PRIORITY`|Priority for low priority tasks, e.g. updating characters.|`7`
`MEMBERAUDIT_TASKS_MAX_ASSETS_PER_PASS`|Technical parameter defining the maximum number of asset items processed in each pass when updating character assets. A higher value reduces duration, but also increases task queue congestion.|`2500`
`MEMBERAUDIT_TASKS_NORMAL_PRIORITY`|Priority for normal tasks, e.g. updating characters.|`5`
`MEMBERAUDIT_TASKS_OBJECT_CACHE_TIMEOUT`||`600`
`MEMBERAUDIT_TASKS_TIME_LIMIT`|Global timeout for tasks in seconds to reduce task accumulation during outages.|`7200`
