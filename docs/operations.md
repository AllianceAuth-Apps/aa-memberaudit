# Operations Manual

## Installation

### Step  0 - Check dependencies are installed

1. Member Audit is a plugin for Alliance Auth. If you don't have Alliance Auth running already, please install it first before proceeding. (see the official [AA installation guide](https://allianceauth.readthedocs.io/en/latest/installation/auth/allianceauth/) for details)

2. Member Audit needs the app [django-eveuniverse](https://gitlab.com/ErikKalkoken/django-eveuniverse) to function. Please make sure it is installed, before before continuing.

### Step 1 - Install app

Make sure you are in the virtual environment (venv) of your Alliance Auth installation. Then install the newest release from PyPI:

```bash
pip install aa-memberaudit
```

### Step 2 - Configure Auth settings

Configure your Auth settings (`local.py`) as follows:

- Add `'memberaudit'` to `INSTALLED_APPS`
- Add below lines to your settings file:

```python
CELERYBEAT_SCHEDULE['memberaudit_run_regular_updates'] = {
    'task': 'memberaudit.tasks.run_regular_updates',
    'schedule': crontab(minute="*/15"),
}
```

- Optional: Add additional settings if you want to change any defaults. See [Settings](#settings) for the full list.

### Step 3 - Finalize App installation

Run migrations & copy static files

```bash
python manage.py migrate
python manage.py collectstatic
```

Restart your supervisor services for Auth

### Step 4 - Update EVE Online API Application

Update the Eve Online API app used for authentication in your AA installation to include the following scopes:

```text
esi-assets.read_assets.v1
esi-bookmarks.read_character_bookmarks.v1
esi-calendar.read_calendar_events.v1
esi-characters.read_agents_research.v1
esi-characters.read_blueprints.v1
esi-characters.read_contacts.v1
esi-characters.read_corporation_roles.v1
esi-characters.read_fatigue.v1
esi-characters.read_fw_stats.v1
esi-characters.read_loyalty.v1
esi-characters.read_medals.v1
esi-characters.read_notifications.v1
esi-characters.read_opportunities.v1
esi-characters.read_standings.v1
esi-characters.read_titles.v1
esi-clones.read_clones.v1
esi-clones.read_implants.v1
esi-contracts.read_character_contracts.v1
esi-corporations.read_corporation_membership.v1
esi-industry.read_character_jobs.v1
esi-industry.read_character_mining.v1
esi-killmails.read_killmails.v1
esi-location.read_location.v1
esi-location.read_online.v1
esi-location.read_ship_type.v1
esi-mail.organize_mail.v1
esi-mail.read_mail.v1
esi-markets.read_character_orders.v1
esi-markets.structure_markets.v1
esi-planets.manage_planets.v1
esi-planets.read_customs_offices.v1
esi-search.search_structures.v1
esi-skills.read_skillqueue.v1
esi-skills.read_skills.v1
esi-universe.read_structures.v1
esi-wallet.read_character_wallet.v1
```

### Step 5 - Verify Celery configuration

Please note that Member Audit **will not work** with the process based celery setup from the official AA installation guide!

If you have not yet switched to a thread-based celery setup, please see this step-by-step guide on how to do so: [Configuring celery workers](#configuring-celery-workers)

### Step 6 - Load Eve Universe map data

In order to be able to select solar systems and ships types for trackers you need to load that data from ESI once. If you already have run those commands previously you can skip this step.

Load Eve Online map:

```bash
python manage.py eveuniverse_load_data map
```

```bash
python manage.py memberaudit_load_eve
```

You may want to wait until the loading is complete before continuing.

```{hint}
These command will spawn a thousands of tasks. One easy way to monitor the progress is to watch the number of tasks shown on the Dashboard.
```

### Step 7 - Enable optional features

Some features are disabled by default. Please review and decide which features you want to enable for your installation:

- Corporation roles: Add `MEMBERAUDIT_FEATURE_ROLES_ENABLED = True` to your local settings.

### Step 8 - Setup permissions

Finally you want to setup permission to define which users / groups will have access to which parts of the app. Check out [permissions](#permissions) for details.

Congratulations you are now ready to use Member Audit!

## Updating

To update your existing installation of Member Audit first enable your virtual environment.

Then run the following commands from your AA project directory (the one that contains `manage.py`).

```bash
pip install -U aa-memberaudit
```

```bash
python manage.py migrate
```

```bash
python manage.py collectstatic
```

Finally restart your AA supervisor services.

## Permissions

For this app there are two types of permissions:

- Feature permissions give access to a feature
- Scope permissions give access to scope

To define a role you will mostly need at least one permission from each type. For example for the recruiter role you will want `finder_access`, that gives access to the character finder tool, and `view_shared_characters`, so that the recruiter can see all shared characters.

The exception is the basic role, `basic_access`, that every user needs just to access the app. It does not require any additional scope roles, so a normal user just needs that role to be able to register his characters.

### Permission list

Name | Description | Type
-- | -- | --
`basic_access`| Can access this app and register and view own characters | Feature
`share_characters`| Can share his characters. Note that others need the <br>`view_shared_characters` permission to see them.  | Feature
`finder_access`| Can access character finder features for accessing characters<br>from others | Feature
`reports_access`| Can access reports features for seeing reports and analytics. | Feature
`characters_access`| Can access characters owned by others. | Feature
`exports_access`| Can access data exports.<br>Warning: This permission gives access to all data from all<br>characters and does not require any additional scope permissions. | Feature
`view_shared_characters`| All characters, which have been marked as shared &<br>can access these characters | Feature & Scope
`view_same_corporation`| All mains - incl. their alts -  of the same corporations<br>the user's main belongs to | Scope
`view_same_alliance`| All mains - incl. their alts -  of the same alliances<br>the user's main belongs to | Scope
`view_everything`| All characters registered with Member Audit | Scope
`notified_on_character_removal` | Get a notification when someone drops a character. | Feature
`view_skill_sets` | Can view skill set for a character. | Scope

```{hint}
All above mentioned permissions can be found under the category "memberaudit | general".
```

### Example Roles

To further illustrate how the permission system works, see the following list showing which permissions are needed to define common roles:

Role | Description | Permissions
-- | -- | --
Normal user | Can use this app and register and access own characters | `basic_access`
Recruiter | Can access shared characters | `basic_access`<br>`finder_access`<br>`view_shared_characters`
Corporation Leadership | Can access reports for his corporation members<br>(but can not access the characters) | `basic_access`<br>`reports_access`<br>`view_same_corporation`
Corp Leadership & Recruiter | Can access shared characters | `basic_access`<br>`finder_access`<br>`view_shared_characters`<br>`reports_access`<br>`view_same_corporation`
Alliance Auditor | Can search for and access all characters of his alliance  | `basic_access`<br>`finder_access`<br>`characters_access`<br>`view_same_alliance`<br>`notified_on_character_removal`

```{note}
Naturally, superusers will have access to everything, without requiring permissions to be assigned.
```

## Management Commands

The following management commands are available to perform administrative tasks:

```{hint}
Run any command with `--help` to see all options
```

### memberaudit_data_export

Export data into a CSV file for use with external applications. Will include data from all characters in the database.

Currently supports the wallet journal only.

### memberaudit_load_eve

Pre-loads data required for this app from ESI to improve app performance.

### memberaudit_reset_characters

This command deletes all locally stored character data, but maintains character skeletons, so they can be reloaded again from ESI.

```{warning}
Make sure to stop all supervisors before using this command.
```

### memberaudit_stats

This command returns current statistics:

- Object counts for all character sections (e.g. asset items)
- Current Member Audit settings
- Current stale minutes configuration

### memberaudit_update_characters

Start updating characters from ESI. You can choose to update all or specific sections.

## Configuring celery workers

Celery workers can be setup in different ways. The two main flavors are thread based and process based. Thread based workers perform better when tasks are primarily I/O bound. And process based workers perform better with tasks that are primarily CPU bound.

AA tasks are primarily I/O bound (most tasks are fetching data from ESI and/or updating the database). That is why thread based setups for AA will usually outperform process based setups by a wide margins in terms of task throughput per CPU second. Some popular community apps, which make heavy use of tasks like Member Audit will not even work properly with a process based setup on most systems.

### Step 1 - Configure workers

```{hint}
The celery worker configuration can be found in the `supervisor.conf` file. This file is usually located in your AA root folder, see same folder where you also find the `manage.py` file. When you followed the default installation guide the path is: `/home/allianceserver/myauth/supervisor.conf`. This file contains the configuration for several programs. The celery worker configuration can be found under `[program:worker]`.
```

The first step is to change the configuration of your celery worker. Here is an example configuration:

```cfg
[program:worker]
command=/home/allianceserver/venv/auth/bin/celery -A myauth worker -P threads -c 10 -l INFO -n %(program_name)s_%(process_num)02d
directory=/home/allianceserver/myauth
user=allianceserver
numprocs=2
process_name=%(program_name)s_%(process_num)02d
stdout_logfile=/home/allianceserver/myauth/log/worker.log
stderr_logfile=/home/allianceserver/myauth/log/worker.log
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
killasgroup=true
priority=998
```

This example configuration will spawn up to 20 concurrent worker threads running on two processes with up to 10 threads each.

Depending on your system you may want to adjust the configuration:

- `numprocs`: Number of processes. Must not be higher then the number of available CPU cores.
- `-c`: Number of threads per process. Can be decreases/increased to adjust how much load the celery workers will utilize.

### Step 2 - Setup memmon

In addition we strongly recommend to setup measures to protect your celery workers from consuming too much memory.

This is not a built in feature and requires the 3rd party extension [superlance](https://superlance.readthedocs.io/en/latest/), which includes a set of plugin utilities for supervisor. The one that watches memory consumption is [memmon](https://superlance.readthedocs.io/en/latest/memmon.html).

To setup install superlance into your venv with:

```bash
pip install superlance
```

You can then add `memmon` to your `supervisor.conf`. Here is an example setup with a worker:

```cfg
[eventlistener:memmon]
command=/home/allianceserver/venv/auth/bin/memmon -p worker_00=512MB -p worker_01=512MB
directory=/home/allianceserver/myauth
events=TICK_60
stderr_logfile=/home/allianceserver/myauth/log/memmon.log
```

This setup will check the memory consumption of two "worker" programs every 60 secs and automatically restart it if is goes above 512 MB. Note that it will use the stop signal configured in supervisor, which is `TERM` by default. `TERM` will cause a "warm shutdown" of your worker, so all currently running tasks are completed before the restart.

This configuration is for exactly two worker processes. If you have more or less, please adjust accordingly.

The 512 MB is just an example and should be adjusted to fit your system configuration. Note that the total memory consumption is the sum of all thresholds per worker process, e.g. here we allow a maximum of 1 GB.

### Step 4 - Update connection pool for ESI

If you have more than 10 worker threads you also need to increase the connection pool for django-esi accordingly. You can do this by adding the following line to your local settings (e.g. for a total of 20 worker threads):

```python
ESI_CONNECTION_POOL_MAXSIZE = 20
```

```{seealso}
See [here](https://gitlab.com/allianceauth/django-esi/-/blob/master/esi/app_settings.py#L36) for the corresponding setting in django-esi.
```

### Step 5 - Enable changes

Finally, to enable all changes your will need to reload your supervisor.

Let's first shutdown your AA programs normally.

```bash
sudo supervisorctl stop myauth:
```

Then we reload the supervisor configuration, which will also restart all programs:

```bash
sudo supervisorctl reload
```

To verify this worked well, you can check the status of your AA programs with:

```bash
sudo supervisorctl status myauth:
```

All programs should be shown with `RUNNING`.

In case you encounter any issues you can find the relevant logs here:

- supervisor: `sudo journalctl -u supervisor`
- worker: `worker.log` in `myauth/log`
- memmon: `memmon.log` in `myauth/log`
- gunicorn: `gunicorn.log` in `myauth/log`

## Configuring update frequency

In general most character sections are updated every 4 hours, with some heavy sections like assets updated every 6 hours, and some sections where more current information is needed, like location, updated every hour.

```{hint}
You can see the current stale minutes configuration for all sections by running the **memberaudit_stats** command.
```

If you have different requirements, you can change the update frequency for each and every section. E.g. decreasing the update frequency will help with reducing the overall task load.

How often a section is updated is determined by their "stale minutes" value. That value defines how long it takes for a section to "turn" stale after it's last successful update was completed. Stale sections will be updated with the next run of the periodic update task, which normally runs every 15 minutes.

To set a custom stale minutes values for a sections add the name of the section and the new value to the `MEMBERAUDIT_SECTION_STALE_MINUTES_CONFIG` setting. That setting is a dict and expects the name of the section as key.

For example let's set the stale minutes for the asset section to 12 hours:

```python
MEMBERAUDIT_SECTION_STALE_MINUTES_CONFIG = {"assets": 720}
```

Multiple entries need to be separated with a comma. For example if we also want to set the stale minutes for the contacts section to 6 hours we get:

```python
MEMBERAUDIT_SECTION_STALE_MINUTES_CONFIG = {"assets": 720, "contacts": 360}
```

```{note}
Sections, which are not defined here will use their default.
```

```{hint}
You can see the current stale minutes configuration for all sections by running the **memberaudit_stats** command.
```

## Settings

Here is a list of available settings for this app. They can be configured by adding them to your AA settings file (`local.py`).

```{note}
All settings are optional and the app will use the documented default settings if they are not used.
```

```{eval-rst}
.. automodule:: memberaudit.app_settings
    :members:
```

## Uninstalling

Here is how you can uninstall Member Audit cleanly from your system.

### Step 1 - Shut down supervisors

First you should shut down all AA services.

```bash
sudo supervisorctl stop myauth:
```

### Step 2 - Remove tables from the database

Next we will remove Member Audit's table from the database.

Important: You will loose all Member Audit related data. You can not undo this step, unless you have a backup.

First, fetch the SQL script:

```bash
wget https://gitlab.com/ErikKalkoken/aa-memberaudit/-/raw/master/memberaudit/tools/drop_tables.sql
```

Next, log into mysql, switch to your database and then and run the script to drop all tables:

```bash
sudo mysql -u root
use alliance_auth;
source drop_tables.sql;
```

Check that all tables have been deleted.

```bash
show tables;
```

Then, switch back to bash and delete the sql script (it has served it's purpose):

```bash
exit;
rm drop_tables.sql
```

Finally, we inform Django that the Member Audit tables have been deleted:

```bash
python manage.py migrate memberaudit zero --fake
```

### Step 3 - Remove app from Django

After the migration to zero is completed, we can now remove the Django app in your local settings.

For that remove the `"memberaudit"` in `INSTALLED_APPS` and any other setting about Member Audit, e.g. definition for tasks.

### Step 4  Uninstall Python package

Finally, we can uninstall the Python package:

```bash
pip uninstall aa-memberaudit
```

### Step 5 - Restart AA services

Member Audit is now fully uninstalled and you can restart your AA services:

```bash
sudo supervisorctl start myauth:
```
