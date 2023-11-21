"""Fix invalid locations in assets caused by issue #153.

This migrations will replace all invalid locations in character assets with the
"unknown location" and delete the invalid locations.
"""

from django.db import migrations

APP_NAME = "memberaudit"


def forwards(apps, schema_editor):
    if schema_editor.connection.alias != "default":
        return

    # Valid locations IDs do not have an asset item with the same ID
    CharacterAsset = apps.get_model(APP_NAME, "CharacterAsset")
    data = CharacterAsset.objects.values("item_id", "location_id")
    asset_item_ids = {obj["item_id"] for obj in data}
    asset_location_ids = {obj["location_id"] for obj in data}
    valid_asset_location_ids = asset_location_ids - asset_item_ids

    # Location which are references by items on other sections are also valid
    Location = apps.get_model(APP_NAME, "Location")
    invalid_locations = (
        Location.objects.exclude(id__in=valid_asset_location_ids)
        .exclude(contract_start_location__isnull=False)
        .exclude(contract_end_location__isnull=False)
        .exclude(characterlocation__isnull=False)
        .exclude(characterjumpclone__isnull=False)
        .exclude(characterwallettransaction__isnull=False)
        .exclude(id=Location.LOCATION_UNKNOWN_ID)
    )
    if not invalid_locations.exists():
        print("No invalid locations to fix. ", end="")
        return

    invalid_assets = CharacterAsset.objects.filter(location__in=invalid_locations)
    print(
        f"Fixing {invalid_assets.count():,} corrupted assets and removing "
        f"{invalid_locations.count():,} invalid locations... ",
        end="",
    )
    unknown_location, _ = Location.objects.get_or_create_esi(
        id=Location.LOCATION_UNKNOWN_ID, token=None
    )
    invalid_assets.update(location=unknown_location)
    invalid_locations.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("memberaudit", "0015_charactership_item_id"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
