# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased] - yyyy-mm-dd

## [3.12.0] - 2024-10-22

>**IMPORTANT**: When updating from a version prior to 3.7.2, 3.6.0, 3.4.0 or 3.0.0 please see the update notes for those versions first!

### Changed

- Removed the scope `esi-mail.organize_mail.v1`. This scope is not used by Member Audit and can therefore be removed without causing any side effects. (#173)

## [3.11.0] - 2024-10-09

>**IMPORTANT**: When updating from a version prior to 3.7.2, 3.6.0, 3.4.0 or 3.0.0 please see the update notes for those versions first!

### Changed

- Reworked skill queue to make it more useful.
- Current skill in training (if any) is now shown in character overview
- Now shows explicitly whether a character's training queue is active

### Fixed

- Skill queue shows wrong skill as active (#142)

## [3.10.0] - 2024-10-07

>**IMPORTANT**: When updating from a version prior to 3.7.2, 3.6.0, 3.4.0 or 3.0.0 please see the update notes for those versions first!

### Added

- Added new corporation roles: Brand Manager, Project Manger & various Deliveries roles

## [3.9.0] - 2024-10-02

>**IMPORTANT**: When updating from a version prior to 3.7.2, 3.6.0, 3.4.0 or 3.0.0 please see the update notes for those versions first!

### Added

- Added protection against using broken ESI endpoints. When an endpoints is reported as down by ESI (i.e. status=red), Member Audit will skip updating the related section, e.g. mails. This should significantly reduce the number of failed tasks and ESI errors generated while endpoints are down. Big thanks to @MrRuthMN for the suggestion. (#170)

## [3.8.1] - 2024-09-17

>**IMPORTANT**: When updating from a version prior to 3.7.2, 3.6.0, 3.4.0 or 3.0.0 please see the update notes for those versions first!

### Changed

- Added django-esi 5.3 as minimum dependency to address a bug in 5.2, that disabled the ability to add characters

## [3.8.0] - 2024-01-31

>**IMPORTANT**: When updating from a version prior to 3.7.2, 3.6.0, 3.4.0 or 3.0.0 please see the update notes for those versions first!

### Added

- New dashboard panel showing interesting KPIs for a users's character, e.g. total wallet ISK or total skillpoints (#154)

### Changed

- Add optional storing of raw ESI data for contract items and bids
- Add tests to prove that contract items are only fetched once (see also #60)

## [3.7.5] - 2024-01-25

>**IMPORTANT**: When updating from a version prior to 3.7.2, 3.6.0, 3.4.0 or 3.0.0 please see the update notes for those versions first!

### Fixed

- memberaudit.tasks.update_character_roles KeyError (#159)

## [3.7.4] - 2024-01-17

>**IMPORTANT**: When updating from a version prior to 3.7.2, 3.6.0, 3.4.0 or 3.0.0 please see the update notes for those versions first!

### Fixed

- CharacterContractItem.record_id has wrong type (#158)

## [3.7.3] - 2024-01-04

>**IMPORTANT**: When updating from a version prior to 3.7.2, 3.6.0, 3.4.0 or 3.0.0 please see the update notes for those versions first!

### Fixed

- High traffic on mails endpoint causing ESI bans (#157)

## [3.7.2] - 2023-12-29

>**IMPORTANT**: When updating from a version prior to 3.6.0, 3.4.0 or 3.0.0 please see the update notes for those versions first!

### Update notes

In version 3.5.0 a bug was introduced, which could cause the creation of invalid EveEntity objects (See also issue #156). These can not be resolved and will remain in your system causing problems. Any other app, which tries to resolve them, will run into exceptions.

To remedy this situation we are providing a tool, which allows you to safely remove these invalid EveEntity objects. The bug itself was fixed with 3.7.1.

Please run the following command after installing this update and follow the onscreen instructions:

```sh
python manage.py memberaudit_fix_eve_entities
```

### Added

- Tool for removing invalid EveEntity objects which were created by issue #156

## [3.7.1] - 2023-12-28

>**IMPORTANT**: When updating from a version prior to 3.6.0, 3.4.0 or 3.0.0 please see the update notes for those versions first!

### Fixed

- Title IDs are wrongly interpreted as EveEntity IDs and create unnecessary ESI errors

## [3.7.0] - 2023-12-21

>**IMPORTANT**: When updating from a version prior to 3.6.0, 3.4.0 or 3.0.0 please see the update notes for those versions first!

### Changed

- Added support for AA4

## [3.6.0] - 2023-12-19

>**IMPORTANT**: When updating from a version prior to 3.4.0, please see the important update notes for 3.4.0 first!

>**IMPORTANT**: When updating from a version prior to 3.0.0, please see the important update notes for 3.0.0 first!

After updating to this new version and completing the restart of your Alliance Auth server, please run the following command to ensure the new home location is properly updated for all characters:

```sh
python manage.py memberaudit_update_characters jump_clones
```

### Update notes

### Added

- Home location now shown for every character on the character viewer (#155)

### Changed

- `memberaudit_update_characters` command extended to also allow selection specific sections to update

## [3.5.3] - 2023-12-14

### Fixed

- When storing of esi data is enabled character updates break with: `AttributeError: 'str' object has no attribute 'value'`

## [3.5.2] - 2023-12-14

### Changed

- Improved instrumentation for storing data received from ESI for debugging. Please see new setting `MEMBERAUDIT_STORE_ESI_DATA_ENABLED` in documentation for details.

### Fixed

- Assets sometimes wrongly classified as changed. This change will reduce the number of asset updates.

## [3.5.1] - 2023-12-14

### Update notes

Please note that this patch contains a migration, which can potentially take 10 minutes or more to complete on larger installations. Please be patient.

### Fixed

- Some child assets are not created (#152)

## [3.5.0] - 2023-12-09

### Update notes

>**Note**: We recommend waiting until all Member Audit tasks in the queue are processed and then installing this update while AA is shut down.

>**IMPORTANT**: When updating from a version prior to 3.4.0, please see the important update notes for 3.4.0 first!

>**IMPORTANT**: When updating from a version prior to 3.0.0, please see the important update notes for 3.0.0 first!

### Changed

- Changes to the character update tasks:
  - You can now define for each character section how it is updated (replaces the former rings approach). For details please see [Configuring update frequency](https://aa-memberaudit.readthedocs.io/en/latest/operations.html#configuring-update-frequency) in the docs.
  - The former generic update task (update_character_section task) has been replace by individual update tasks for each section, which should make monitoring and trouble shooting much easier
  - Performance has been improved for many update tasks: contact labels, loyalty, mail, points, planets, standings, titles
  - Now also records start and finish time for when sections where actually updated, due to changes

- **memberaudit_stats** has been fixed and reworked. It now shows the following:
  - current objects counts for all sections
  - current Member Audit settings
  - current configuration for section stale minutes (i.e. how often sections are updated)
  - update static (e.g. average duration for updating a specific section)
  - Task statistics have been removed incl. the related setting ``MEMBERAUDIT_LOG_UPDATE_STATS``. We recommend using [Task Monitor](https://apps.allianceauth.org/apps/detail/aa-taskmonitor) for gathering task statistics

- Fixed and improved **memberaudit_reset_characters** command
- Added "ignore_stale" feature to update_character tasks
- "Force update" now means "updating despite no change" only and no longer ignores stale status
- Refactoring
- Improved test suite

## [3.4.4] - 2023-12-01

>**IMPORTANT**: When updating from a version prior to 3.4.0, please see the important update notes for 3.4.0 first!

>**IMPORTANT**: When updating from a version prior to 3.0.0, please see the important update notes for 3.0.0 first!

## Update notes

This patch release fixes a major bug (#153), which causes the creation of invalid locations and the corruption of asset and other character data. To repair the data corruption, please follow the process below, which includes running a special repair command: [^1]

>**Important**: We strongly recommend to run the repair command while your AA instance is shutdown. Otherwise the command might take much longer to complete or could even fail.

### Step 1 - Shutdown AA

With your sudo user please first shutdown your AA instance:

```sh
sudo supervisorctl stop myauth:
```

### Step 2 - Backup your database

We recommend you make a full backup of your database before proceeding. Here is one easy way to do it:

```sh
sudo mysqldump -u root alliance_auth > alliance_auth.sql
```

### Step 3 - Run repair command

Then, after switching to your AA user, you can start the repair command with:

```sh
python /home/allianceserver/myauth/manage.py memberaudit_fix_locations
```

Note that details will be logged to the extensions log. You can filter for relevant log entries only like so:

```sh
grep memberaudit_fix_locations log/extensions.log
```

Should the repair command fail to remove all invalid locations you can try running the command again. If that stills fails, you might want to try again after one complete update cycle with this patch has completed.

Should you run into any issues you can increase logging verbosity or exclude problematic locations via parameters to the repair command. Please run the command with `-h` for details.

### Step 4 - Start AA instance again

After the command is finished, you can start your your AA instance again with:

```sh
sudo supervisorctl start myauth:
```

Finally, the update tasks for the affected characters need to complete, before the data repair is finally done.

[^1]: We assume you have a standard installation from the official installation guide (aka "bare metal"). The syntax for a docker installation might differ.

## Changed

- Moved updates notes to this entry

## Fixed

- Typo in log messages of repair tool

## [3.4.4b2] - 2023-11-29

## Fixed

- Fix attempt: The fix locations command aborts with DB error: `Server has gone away` on a large installations (i.e. ~6K characters)

## [3.4.4b1] - 2023-11-29

## Added

- Special command `memberaudit_fix_locations` to repair data corruptions caused by #153

## [3.4.3] - 2023-11-29

>**IMPORTANT**: When updating from a version prior to 3.0.0, please see the important update notes for 3.0.0 first!

>**IMPORTANT**: When updating from a version prior to 3.4.0, please see the important update notes for 3.4.0 first!

## Changed

- Searches in character finder match against full names instead of just beginning
- Improved category filter for Locations
- Improved test suite for asset updates

## Fixed

- Some parent assets are apparently not created in time for when the related child assets are created. (#152)
- Can no longer see contents of asset containers (#153)
- Asset update recorded as success even when there are assets leftover

## [3.4.2] - 2023-11-16

>**IMPORTANT**: When updating from a version prior to 3.0.0, please see the important update notes for 3.0.0 first!

>**IMPORTANT**: When updating from a version prior to 3.4.0, please see the important update notes for 3.4.0 first!

### Update notes

Please run a manual update for all titles to make sure this change is applied consistently. You can start the manual update on the admin page for Characters. Select all characters that need to be updated and then perform the action "Update titles for selected characters".

## Changed

- Removed XML tags from titles
- Titles are now shown in the same order as in the Eve client

## [3.4.1] - 2023-11-16

>**IMPORTANT**: When updating from a version prior to 3.0.0, please see the important update notes for 3.0.0 first!

>**IMPORTANT**: When updating from a version prior to 3.4.0, please see the important update notes for 3.4.0 first!

## Fixed

- Not all titles showing for characters (#151)

## [3.4.0] - 2023-11-16

>**IMPORTANT**: When updating from a version prior to 3.0.0, please see the important update notes for 3.0.0 first!

### Update notes

For the current ship asset to be included correctly you need to force an update of ships for all characters. You can start the manual update on the admin page for Characters. Select all characters that need to be updated and then perform the action "Update ship for selected characters".

### Changed

- Undocked ships are now automatically included in a character's assets. This means that the asset filter should not longer fail, when a corresponding ship is undocked. (#150)
- Modernization and refactoring of tests

### Fixed

- Limit retries and add exponential backoff with jitter to updating structures and mail entities. This should prevent the situation where structure update tasks run into ESI errors repeatedly and build up.

## [3.3.3] - 2023-10-14

>**IMPORTANT**: When updating from a version prior to 3.0.0, please see the important update notes for 3.0.0 first!

### Changed

- Removed default permissions from MailEntity

### Fixed

- Added missing default permissions for skil set related models

## [3.3.2] - 2023-10-12

>**IMPORTANT**: When updating from a version prior to 3.0.0, please see the important update notes for 3.0.0 first!

### Changed

- Update actions for characters on the admin site now also include skills and skill sets
- Show one message only to users when updating multiple characters on admin page

### Fixed

- Reduced page load time for user compliance report

## [3.3.1] - 2023-10-09

>**IMPORTANT**: When updating from a version prior to 3.0.0, please see the important update notes for 3.0.0 first!

### Changed

- Added and improved tests

## [3.3.0] - 2023-10-08

>**IMPORTANT**: When updating from a version prior to 3.0.0, please see the important update notes for 3.0.0 first!

### Added

- Corporation titles are now shown for all characters

### Changed

- query name for CorporationRole.character FK changed from `role` to `roles`

## [3.2.0] - 2023-10-08

>**IMPORTANT**: When updating from a version prior to 3.0.0, please see the important update notes for 3.0.0 first!

### Added

- Localization to Ukrainian (🇺🇦)

### Changed

- Update to localizations

## [3.1.0] - 2023-10-05

>**IMPORTANT**: When updating from a version prior to 3.0.0, please see the important update notes for 3.0.0 first!

### Added

- Show admin action for updating most sections for characters

### Changed

- Re-activated corporation histories

## [3.0.0] - 2023-10-04

### Update notes

This major release adds corporation roles as new feature. To make migration easier this new feature is disabled by default and need to be enabled through a setting.

### Enabling corporation roles

You can enable corporation roles by adding the following line to your local setting and then restarting Auth:

```python
MEMBERAUDIT_FEATURE_ROLES_ENABLED = True
```

!! Please note that once enabled users will need to re-register their characters to be able to use it !!

This is necessary, because this new feature requires an additional ESI scope. Users will automatically be asked to re-register via Auth notification (If you have the app Discord Notify enabled, those notification will be forwarded automatically as DMs to users on Discord). Users will also be informed through a note on the characters launch page and through a new status icon next to the character name.

Please note that this scope change will not disrupt the update of existing characters. The update status of a character which only issue is the missing esi scope will show with update status "Limited Token" on the admin site, but otherwise all characters will continue to be updated normally.

### Migration approaches

As explained in the previous article all users need to re-register their characters in order to use the new feature. There are two migration approaches:

- Managed migration
- Unmanaged migration

#### Managed migration

The first approach is a managed migration which attempts to migrate all characters by a deadline. The approach would look something like this:

1. Inform all users that they need to re-register their characters until a deadline
1. Enable the new feature at the deadline
1. Allow users a grace period to re-register their characters
1. After that grace period is passed, start pushing stragglers to re-register

This approach requires active communication with the users and is very visible, but should ensure most characters are migrated within a short time.

#### Unmanaged migration

Alternatively, an unmanaged migration is possible by turning off the automatic notification to users about token errors. Then users will (hopefully) re-register their characters over time once they see the related warnings on the launchers page.

The related settings are:

```python
MEMBERAUDIT_NOTIFY_TOKEN_ERRORS = False
```

This approach is does not require much (or any) communication with the users. However, it can take a long time before a significant amount of existing characters are migrated to the new feature.

### Monitoring the migration

You can monitor the progress of the migration on admin site by looking at the update status of the Member Audit characters (the page under "Member Audit / Characters").

Here is an example:

![update_status](https://imgpile.com/images/DlGvdM.png)

The relevant values are:

- "Limited Token": are characters which have not re-registered yet
- "Incomplete": have not been updated yet after enabling the roles feature
- "In Progress": are currently being updated
- "OK": have completed updating after re-registering with the new scope

You goal for the migration is to convert all characters which have "Limited Token" to "OK". At least for characters belonging to a non-guest state.

### Added

- Corporation roles are now shown for characters. This new feature can be enabled via the setting: `MEMBERAUDIT_FEATURE_ROLES_ENABLED`
- Token errors are now handled automatically: The user is notified and update for the related character section is suspended until the user re-registered the character. The automatic notification can be disabled with the setting `MEMBERAUDIT_NOTIFY_TOKEN_ERRORS`
- Users are now asked to re-register characters that have a token error on the launcher page
- New status tag shown next to the character name on launcher and viewer inform about an update issue
- New status tag and detailed error description shown on each character tab informs about an update issue

## Changed

- App badge now also includes the count of characters with token errors and disabled characters
- New update status "Limited token" shown on the admin page for characters which have a token issue on one section only (e.g. because a new role scope missing)

## [2.11.3] - 2023-09-21

### Changed

- Improved the way entity IDs are resolved to names for all sections, e.g. resolving IDs will not spawn additional tasks and will resolve the new IDs from the related objects only

## [2.11.2] - 2023-09-15

### Fixed

- Admin action for updating location and online status are not working (#148)
- Made task arguments non-optional when used with celery_once keys feature

## [Unreleased] - yyyy-mm-dd

## [2.11.1] - 2023-09-10

### Fixed

- DELETE on large data structures hangs and deletion is cancelled (#146)

## [2.11.0] - 2023-09-04

### Added

- Added mandatory pylint checks

### Changed

- Refactoring to address pylint issues

## [2.10.1] - 2023-07-11

### Changed

- Adds missing index for CharacterStanding
- Applies some minor improvements that require a new migration

## [2.10.0] - 2023-07-11

### Added

- NPC standings for agents, corporations and factions (#143)

## [2.9.4] - 2023-07-05

### Changed

- Use ellipsis instead of a scrollbar for character sidebar (!94) - Thanks @ppfeufer

## [2.9.3] - 2023-07-05

### Changed

- Removed local swagger spec file
- Tasks no longer fail during downtime
- Refactored ESI available handling for tasks into decorator

### Fixed

- Attempt: Extend params for task update_character_mail_bodies()
- Prevent character names overflowing the sidebar menu (!92) - Thanks @maxtsero!
- Characters no longer wrap in sidebar

## [2.9.2] - 2023-06-30

### Fixed

- Datatable for PI in character viewer does not load (#145)

## [2.9.1] - 2023-06-20

### Changed

- All character sections will now skip storing the data if it has not changed
- Refactor character section updates (!88)
- Refactor and improve codebase (!89)

## [2.9.0] - 2023-06-16

### Update notes

Users now need the new permission `view_skill_sets` in order to see the skill sets for a character. Please add this new permission to your states / groups accordingly (e.g. to the Member state). The rational behind this change is that is allows alliances to hide their doctrine fits from guests and new recruits.

### Added

- Show by whom and when a skill set was last modified
- Show by whom and when a skill set group was last modified
- New permission `view_skill_sets`
- New tab showing a characters PI planets
- Ability to clone existing skill sets (#130)

### Changed

- Viewing skill sets for characters now require the new permission `view_skill_sets` (#130)
- All character sections tabs now have a title
- "Mining" tab now under "Industry"
- "Attributes" tab now under "Skills"
- Switched to flit build tool

### Fixed

- Skillpoints Data Mislabeled (#141)

## [2.8.1] - 2023-05-09

### Changes

- Some fixes of translation strings
- Additional Russian translations (now 100%)

## [2.8.0] - 2023-05-08

### Added

- Localization for Russian
- Uninstall chapter to docs
- Support for Python 3.11

## [2.7.0] - 2023-04-19

### Changed

- Added language support for more languages incl. Ukrainian
- Add localization for models visible on admin site, e.g. Character
- Moved build process to PEP621
- Improved tests and test coverage

## [2.6.3] - 2023-04-16

### Changed

- Added more localizations

## [2.6.2] - 2023-04-11

### Fixed

- Template files are missing from the distribution package

## [2.6.1] - 2023-04-08 [YANKED]

### Changed

- Added copy button to bash commands on docs

### Fixed

- Various bugfixes and improves to EFT parser

## [2.6.0] - 2023-03-23

- Show Faction warfare stats for all characters
- Reduce extreme task buildups when ESI errors occur
- Replace outdated project configuration for package installations

### Added

- Faction Warfare stats are now shown for every character on the character viewer
- Ability to set the default task priorities via settings

### Changed

- Priority for update tasks reduced to 7 when started from periodic task
- Child tasks now use inherit their priority from parent tasks, i.e. when doing a character update from the admin page or adding a new character, then all tasks run with higher priority then during regular updates
- Character update tasks are no longer retried automatically when there is an ESI issue. This was causing huge task buildup when ESI was not having problems. Also this should not be needed, since all character updates are automatically repeated every hour or so.
- Will ignore the occasional HTTP 500 error from the loyalty endpoint and log warning (#135)
- Will ignore occasional http 500 for ship endpoint and log warning (#138)
- Temporarily disabled corporations tab, since the ESI endpoint is currently not functioning
- Users are no longer able to skip upgrading to 2.0 first when upgrading from 1.x to prevent migrations failures
- Switching setup configuration to PEP 517 / setup.cfg
- Adding pyproject.toml
- Moving flake8 config to setup.cfg
- Moving isort config to setup.cfg
- Switch to "build" for building deploy package

## [2.5.0] - 2023-02-23

>**Important**:<br>This release requires Alliance Auth 3+. Please make sure to upgrade to Alliance Auth 3+ in case you have not yet done so.

### Added

- General
  - Characters can be disabled and enabled. Disabled characters are not updated.
  - Characters which no longer have an owner are disabled automatically
  - Disabled characters are automatically re-enabled when user adds them again

- Admin page for characters
  - Ability to manually disable (and re-enable) sync for characters
  - New column "Update Status" for characters on the admin page giving better information:
    - OK: Update complete and successful
    - In Progress: Update is currently ongoing
    - Incomplete: Some sections are missing completely. This is usually an issue.
    - Error: An error occurred during the update
    - Disabled: Sync for this character was disabled
  - New filter with counts for update status
  - "No Main" added to State filter and also now showing counts

### Changed

- Drops support for Alliance Auth < 3.0.0 / Django 3
- Base URL now generates a proper slug when a custom app name is used that contains non-Latin characters, e.g. Korean (!67) - @ppfeufer

## [2.4.2] - 2023-01-31

### Changed

- Reverted back to SQLite for tox tests

### Fixed

- Applied workaround for chained task priority

## [2.4.1] - 2022-11-05

### Fixed

- Character sync fails when more then 10 jump clones (!68)

## [2.4.0] - 2022-10-21

### Added

- Send notifications when a character is removed by a user (#128)
- Show ISK total per location on asset tab

Big thanks to @arctiru for the feature contributions!

## [2.3.0] - 2022-10-13

### Added

- Show mining ledger for characters

### Changed

- Full text search on character admin page now includes main characters
- Consolidated skill related tabes into one super tab
- Consolidated clone related tabes into one super tab

## [2.2.3] - 2022-10-11

### Changed

- Re-added references to replaced migrations, which are needed by apps depending on Member Audit

## [2.2.2] - 2022-10-11 (YANKED)

### Changed

- Removed obsolete migrations

## [2.2.1] - 2022-10-11

### Changed

- Removes auto retry for ESI and OS errors, since django-esi already retries all relevant errors

## [2.2.0] - 2022-10-10

### Changed

- Removed support for Python 3.7
- Added support for Python 3.10

### Fixed

- Searching for Toon in Admin Bug (#129)

## [2.1.1] - 2022-09-03

>**Important**:<br>In case you have not updated to Member Audit 2.x yet, please follow the special update instructions for updating to 2.0.0 first, before installing this update!

### Fixed

- Importing skill plans can break when there are more then once skill type with the same name

## [2.1.0] - 2022-09-03

>**Important**:<br>In case you have not updated to Member Audit 2.x yet, please follow the special update instructions for updating to 2.0.0 first, before installing this update!

### Added

- Ability to create skill sets from imported skill plans

### Changed

- Error handling more user friendly when importing EFT fitting

## [2.0.1] - 2022-09-02

>**Important**:<br>In case you have not updated to Member Audit 2.x yet, please follow the special update instructions for updating to 2.0.0 first, before installing this patch!

### Changed

- Improved retry regime when ESI is down

## [2.0.0] - 2022-08-16

This release includes a major change to Member Audit's database structure and therefore requires some additional care when updating. Therefore please follow our special update instructions below.

>**Important**:<br>This is a mandatory update. All future releases will be built upon this version.

>**Hint**:<br>Should you run into any issues and need help please give us a shout on the AA Discord (#community-packages).

### Update instructions

Please follow these instructions for updating Member Audit from 1.x. If you are already on 2.0.0 alpha you can ignore these special instructions.

1. Make sure you are on the latest stable version of Member Audit (1.15.2): `pip show aa-memberaudit`
1. Make sure your current AA installation has no error: `python manage.py check`
1. Shut down your AA instance completely: `sudo supervisorctl stop myauth:`
1. Optional: If you have any additional services that are connected with your AA instance (e.g. Discord bots) shut them down too.
1. Clear your cache: `sudo redis-cli flushall;`
1. Backup your AA database with your standard procedure (or use the example procedure shown below)
1. Install the update: `pip install aa-memberaudit==2.0.0`
1. Verify that the installation went through without any errors or warnings by checking the console output of the last command
1. Run migrate: `python manage.py migrate`
1. Verify that the migration went through without any errors or warnings by checking the console output of the last command
1. Copy static files: `python manage.py collectstatic --noinput`
1. Check for any errors: `python manage.py check`
1. When you have no errors: Restart your AA instance: `sudo supervisorctl start myauth:`

### AA database backup

You can do a complete backup of your database by running the following commands:

1. Make sure your services are completely shut down
1. Dump the whole database to a single file: `sudo mysqldump alliance_auth -u allianceserver -p > alliance_auth.sql`

### Added

- Characters and their (historical) data remain in the system, even after the related tokens have been revoked by the Character's owner.
- Characters loose their user relation and become "orphans" in AA after their token have been revoked. These orphans can now be found through the character finder.

## [2.0.0-ALPHA] - 2022-07-24

### Update notes

We are releasing this update as alpha to gather stability feedback and to ensure this update works across all commonly used environments for Alliance Auth.

>**Important**:<br>Please only install this update if you feel comfortable with potentially having to restore your data in case of issues.

This update has been successfully completed on different installations including in production. And just in case something goes wrong we are providing you with a restore procedure that allows you to fully restore your previous version and data.

Should you run into any issues and need help please give us a shout on the AA Discord (#community-packages).

Please kindly give us feedback about the result of your alpha test and what environment you used (e.g. Ubuntu 18.04 with Maria DB 10.5 and Alliance Auth 2.12.1), so we can determine when to release this version as stable.

#### Updating

Please follow the these steps to install this update:

1. Make sure you are on the latest stable version (1.15)
1. Shut down your AA instance completely: `sudo supervisorctl stop myauth:`
1. Optional: If you have any additional services that are connected with your AA instance shut them down too.
1. Clear your cache: `sudo redis-cli flushall;`
1. Backup your Member Audit tables into a folder of your choice: `sudo mysql alliance_server -u allianceserver -p -N -e 'show tables like "memberaudit\_%"' | sudo xargs mysqldump alliance_server -u allianceserver -p > memberaudit_backup.sql`
1. Optional: Backup tables of apps dependent on Member Audit if applicable, e.g. Mail Relay, aa-memberaudit-securegroups
1. Install the alpha release: `pip install aa-memberaudit==1.16.0a1`
1. Verify that the installation run through without any errors or warnings
1. Run migrate: `python manage.py migrate`
1. Verify that the Django migrations went through without showing any errors or warnings
1. Verify that all migrations for Member Audit have been enabled, including `0012`: `python manage.py showmigrations memberaudit`
1. Restart your AA instance: `sudo supervisorctl start myauth:`
1. Open Member Audit and the character finder for a sample character to verify that the data has been migrated correctly.

#### Restore (optional)

In case your update failed here is how you can restore your previous stable version and data:

1. Shut down your AA instance: `sudo supervisorctl stop myauth:`
1. Clear your cache: `sudo redis-cli flushall;`
1. Migrate Member Audit to zero: `python manage.py migrate memberaudit zero --fake`
1. Delete Member Audit tables by running the `drop_tables.sql` script provided under `memberaudit/tools` e.g. with: `sudo mysql -u allianceserver -p alliance_server < drop_tables.sql`
1. Re-install the latest stable version: `pip install aa-memberaudit==1.15.0`
1. Run migrate: `python manage.py migrate`
1. Re-load your data backup for Member Audit: `sudo mysql -u allianceserver -p alliance_server < memberaudit_backup.sql`
1. Optional: Re-load your data backup for dependant apps OR manually delete tables of dependant apps, migrate them to zero faked then run migrate again to create fresh tables
1. Restart your AA instance: `sudo supervisorctl start myauth:`

### Changed

(see stable release)

## [1.16.0a1] - 2022-06-15

Due to the breaking changes introduced by this new release for 3rd party apps, we will change the version to 2.0.0.
2.0.0a1 is the next release and update after 1.16.0.a1, which also includes the changes from 1.15.1.

## [1.15.2] - 2022-08-07

### Added

- Backwards compatible test factory for creating Character objects for 3rd party apps

## [1.15.1] - 2022-08-06

### Added

- Extended API to make upcoming model change transparent for 3rd party apps

## [1.15.0] - 2022-07-22

### Added

- Display unallocated skillpoints (#121)
- Display injected (but untrained) skills on character sheet (#122)

### Changed

- Operations and user manual moved to Sphinx docs on rtd
- Swagger spec updated (#119)

## [1.14.4] - 2022-07-14

### Fixed

- XSS vulnerability in character bio and emails

Big thanks to @marnvermuldir for finding and fixing this issue!

## [1.14.3] - 2022-06-17

### Changed

- Switch to local SWAGGER spec file

### Fixed

- Add test data to distribution package

## [1.14.2] - 2022-04-11

### Fixed

- Do not show type ID in name of skills in character skill list

## [1.14.1] - 2022-04-06

### Fixed

- Not all shared characters are shown in character finder

## [1.14.0] - 2022-04-01

### Added

- Ability to filter the skill report to only main characters (#110)

Big thanks to @buymespam for the contribution!

### Changed

- Big performance improvement of character finder page for large data sets (>1000 characters)

## [1.13.0] - 2022-03-30

### Added

- Ability to see unregistered characters in character finder

### Changed

- Removed location from character finder
- Handle Asset Safety as special location

### Fixed

- Creating skill sets from fittings are missing skills (required skill 4, 5, 6 if any)
- Show characters being currently updated with status unknown instead of issue

## [1.12.1] - 2022-03-21

### Changed

- Improved performance for admin sites: character, location
- Characters with update issues can now be found by sorting the column "last_update_ok" instead of a filter

## [1.12.0] - 2022-03-18

### Added

- Ability to copy missing required skills to the clipboard, so they can be imported into the skill queue in the Eve client.

## [1.11.1] - 2022-03-16

### Fixed

- Re-enable modal for showing skill set skills for character

## [1.11.0] - 2022-03-16

>**Update note**:<br>Please make sure to re-run the `memberaudit_load_eve` command, which will pre-load types needed to process fittings. Otherwise importing fittings can take a long time.

### Fixed

- Contract Times Should Not be Localized (#108)

## [1.11.0b5] - 2022-03-15

### Changed

- Improved performance of skill set reports page
- Improved performance of character launcher page

## [1.11.0b4] - 2022-03-14

### Changed

- Improved performance of character skill sets tab, character implants tabs, character viewer main page

## [1.11.0b3] - 2022-03-13

### Changed

- Technical improvements (!38)

## [1.11.0b2] - 2022-03-12

### Added

- Ability to define a different name when creating a skill set from a fitting
- Ability to add new skill set to group when creating from fitting

### Changed

- Improved performance of admin site pages for skill sets and skill set groups

### Fixed

- Fail to parse fittings from Eve client with missing slots correctly (#111)

## [1.11.0b1] - 2022-03-10

>**Update note**:<br>Please make sure to re-run the `memberaudit_load_eve` command, which will pre-load types needed to process fittings. Otherwise importing fittings can take a long time.

### Added

- Ability to create skill sets from imported fittings in EFT format via copy & paste from PYFA or Eve Client

## [1.10.0] - 2022-03-05

### Added

- Compliance Groups: You can now ensure that only users who have registered all their characters have access to services. For details please see the respective section in the README / User Manual.

## [1.9.4] - 2022-03-02

### Changed

- Update dependencies for AA 3 compatibility

## [1.9.3] - 2022-03-01

### Changed

- Update dependencies for Django 4 compatibility

## [1.9.2] - 2022-02-12

### Changed

- Improved rendering of bios and mails. Now fully supports font sizes and most links. Colors are ignored on purpose to ensure good readibility with both light and dark theme.

## [1.9.1] - 2022-02-04

### Fixed

- Shared characters that lost the sharing permission are automatically unshared

## [1.9.0] - 2022-01-24

### Added

- Ability to download data export files directly from the web site.

### Changed

- Restricted access with `view_same_corporation` and `view_same_alliance` to affiliations from main character only (#106)
- Removed support for outdated Python 3.6 & Django 3.1

## [1.8.0] - 2022-01-19

### Added

- Data export tool now also supports contracts and contract items

## [1.7.1] - 2022-01-08

### Changed

- Recruiters can now only see character that are shared and if the owning user has the "share_characters" permission. Use case: When only guests can share they charactes, recruiters now automatically loose access to their charactes, one a guest becomes a member.

## [1.7.0] - 2022-01-08

### Added

- Link to directly open character viewer for main characters from compliance report. This allows you to see quicly which characters are missing for full compliance, because the sidebar shows which characters are not registered.

### Changed

- Own user is always shown in reports

## [1.6.0] - 2021-12-19

### Added

- Show reason in wallet journal
- New management command for exporting data as CSV files

### Fixed

- Store reason when syncing wallet journal entries

## [1.5.1] - 2021-11-21

### Fixed

- Error when trying to delete users from memberaudit (or auth) (#104)

## [1.5.0] - 2021-11-12

### Added

- Now also shows current ship of a character in the character viewer

## [1.4.1] - 2021-11-05

### Changed

- Added CI tests for AA 2.9 / Django 3.2

### Fixed

- Character Viewer Wallet panel not sorting correctly (Issue #103)

## [1.4.0] - 2021-07-01

### Added

- Will now send daily reminder notifications to users if their character tokens become invalid.

## [1.3.3] - 2021-06-30

### Changed

- Will no longer run updates during the daily downtime

### Fixed

- Trying to update a character on admin site gives error 500

## [1.3.2] - 2021-05-18

### Fixed

- Trying to fetch deleted mail results in 404s repeatedly (#94)

## [1.3.1] - 2021-05-04

### Changed

- Permissions `view_same_corporation` and `view_same_alliance` will now give access to other characters from **all** corporations / alliances the user's characters belong to. Not only the main character.

### Fixed

- Trying to delete a character from the admin site results in timeouts.
- Make badges fit into the menu

## [1.3.0] - 2021-04-17

### Added

- Show attributes for characters

### Changed

- Disabled fetching EveAncestry objects since current ESI bug is causing HTTP errors. See also: <https://github.com/esi/esi-issues/issues/1264>
- Performance tuning for various view queries

Big thanks to @gray_73 for the feature contribution!

### Fixed

- Added missing tables to drop_tables SQL

## [1.2.1] - 2021-02-18

### Added

- Added user state information to user compliance and skill set reports

### Changed

- Removed guests from user compliance report
- Removed guests from corporations compliance reports
- Removed guests from skill set reports
- Character sidebar now also shows unregistered characters
- Clicking on unaccessible characters in the character sidebar on longer links to a "no permission" page; instead the link has been removed.

## [1.2.0] - 2021-02-16

### Added

- New details window for skill sets showing in detail which skills need to be trained
- New report for corporation compliance
- Additional filters for the character finder

### Changed

- Moved utils into it's own distribution package: allianceauth-app-utils

Thank you @gray_73 for your contribution to this release.

## [1.1.1] - 2021-01-29

### Added

- Additional filters and columns for character finder

### Changed

- Switched from local to on-demand swagger spec
- Improved protection of tasks against ESI outage and exceeded ESI error limits

## [1.1.0] - 2021-01-25

### Added

- Wallet transactions ([#88](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/88))
- Red/green coloring of wallet amounts like in the Eve client

## [1.0.2] - 2021-01-22

### Changed

- Refactor and split models ([#66](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/66))

### Fixed

- Incompatible with django-redis-cache 3.0 ([#90](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/90))

### Changed

## [1.0.1] - 2021-01-16

### Changed

- Performance improvements for update tasks ([#85](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/85))
- Improved resilience against ESI timeouts during transactions ([#87](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/87))
- Improved protection against 420 error when running an update ([#83](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/83))

### Fixed

- Layout error for user with no main in reports ([#86](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/86))

## [1.0.0] - 2021-01-05

### Fixed

- Shows correct icons for BPC and BPOs
- SkillSet reports: 'NoneType' object has no attribute 'portrait_url' ([#81](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/81))

## [1.0.0b3] - 2020-12-24

### Added

- Data retention limits for mail, contracts, wallet ([#75](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/75))
- Show and filter NPCs/agents in contact list ([#63](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/63))
- Autocomplete drop-down for skills and ship_type in skill sets
- Improved statistics with memberaudit_stats
- More filters and better sorting on admin site

### Changed

- Default values for MEMBERAUDIT_UPDATE_STALE_RING_x now rounded to full hours

### Fixed

- Require minimum version of django-eveuniverse for fix ([#71](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/71))
- Icon for SKINs not shown in assets and contracts ([#50](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/50))
- Workaround to prevent character details update aborts ([#77](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/77))

## [1.0.0b2] - 2020-12-14

### Update notes

The feature for sharing ones characters now requires the new permission `share_characters`. To keep the sharing feature enabled, please make sure to assign this new permission accordingly (e.g. to the guest state).

### Added

- `App_totals` added to **memberaudit_stats** command

### Changed

- Only users with the new permission `share_characters` can share their characters. ([#69](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/69))

### Fixed

- Non existing user are marked as compliant ([#59](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/59))
- Character encoding/escaping ([#60](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/60))
- Corp history not reading correctly ([#68](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/68))
- Workaround to deal with broken ESI ancestry endpoint. ([#70](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/70))

## [1.0.0b1] - 2020-12-07

### Change

- Updated README for beta release

### Fixed

- Fixed tox issue related to new PIP dependency resolver

## [1.0.0a15] - 2020-12-06

### Change

- Re-designed doctrines to the much broader concept of skill sets ([#58](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/58))

## [1.0.0a14] - 2020-12-04

### Change

- Former mailing lists  ([#57](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/57))
- More options for management commands

### Fix

- Asset update fails to report success when there was no change

## [1.0.0a13] - 2020-12-03

### Fix

- Stale identification not fully aligned with periodic update tasks

## [1.0.0a12] - 2020-12-03

### Added

- Ability to get measured durations of update process for system tuning

### Fixed

- Sorting order of characters on admin site

## [1.0.0a11] - 2020-12-02

### Changed

- Access to other characters require new permission (except for shared characters) ([#49](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/49))

## [1.0.0a10] - 2020-12-01

### Changed

- Further improvement of the asset update process ([#56](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/56))

## [1.0.0a9] - 2020-11-30

### Changed

- Reduce update load by enabling skipping of updates when data has not changed

## [1.0.0a8] - 2020-11-28

### Fixed

- Assets update process is visible to the user ([#56](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/56))

## [1.0.0a7] - 2020-11-25

### Changed

- don't show permissions we don't use ([!4](https://gitlab.com/ErikKalkoken/aa-memberaudit/-/merge_requests/4))

### Fixed

- Handle ESI error from resolving mailing lists as sender in mails ([#54](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/55))

## [1.0.0a6] - 2020-11-20

### Changed

- Changed approach: Structure resolving exceeds ESI error rate limit ([#53](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/53))

## [1.0.0a5] - 2020-11-19

### Fixed

- Fix to be confirmed: Structure resolving exceeds ESI error rate limit ([#53](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/53))

## [1.0.0a4] - 2020-11-18

### Fixed

- Unknown mailing list IDs are crashing mail update and halting EveEntity ID resolution for all apps ([#51](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/51))
- Wrong character count in compliance report ([#52](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/52))

## [1.0.0a3] - 2020-11-17

### Fixed

- Can't see alts of other alliance mains ([#45](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/45))
- Change report restriction ([#49](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/49))

## [1.0.0a2] - 2020-11-14

### Added

- Add durations to corp history ([#43](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/42))

### Fixed

- Attempt: Fix not-yet-loaded mail behavior ([#40](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/42))
- Disable vertical slider for tables in character finder, reports ([#40](https://gitlab.com/ErikKalkoken/aa-memberaudit/issues/41))

## [1.0.0a1] - 2020-11-12

### Added

- Initial alpha release

---
