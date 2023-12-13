"""Script for generating invalid locations to test fix for issue #153."""

from app_utils.scripts import start_django

start_django()


def main():
    from django.db.models import Max
    from eveuniverse.models import EveEntity, EveType

    from allianceauth.eveonline.models import EveCharacter

    from memberaudit.models import Character, Location
    from memberaudit.tests.testdata.constants import EveTypeId
    from memberaudit.tests.testdata.factories import (
        create_character,
        create_character_asset,
        create_character_contract_courier,
        create_character_jump_clone,
        create_character_jump_clone_implant,
        create_character_location,
        create_character_wallet_transaction,
        create_location,
    )

    EVE_CHARACTER_ID = 91224790  # CCP Seagull

    def max_location_id():
        max_location_id = Location.objects.aggregate(Max("id"))["id__max"]
        return max_location_id

    locations = Location.objects.filter(
        eve_type__isnull=False, eve_solar_system__isnull=False
    )
    valid_location_1 = locations.first()
    valid_location_2 = locations.last()
    if not valid_location_1 or valid_location_1 == valid_location_2:
        raise RuntimeError("Need two valid locations to exist")

    character_entity = EveEntity.objects.filter(
        category=EveEntity.CATEGORY_CHARACTER
    ).first()
    if not character_entity:
        raise RuntimeError("Need a character in eve entities to exist")

    corporation_entity = EveEntity.objects.filter(
        category=EveEntity.CATEGORY_CORPORATION
    ).first()
    if not corporation_entity:
        raise RuntimeError("Need a corporation in eve entities to exist")

    try:
        eve_character = EveCharacter.objects.get(character_id=EVE_CHARACTER_ID)
    except EveCharacter.DoesNotExist:
        eve_character = EveCharacter.objects.create_character(
            character_id=EVE_CHARACTER_ID
        )

    Character.objects.filter(eve_character=eve_character).delete()
    character = create_character(eve_character, is_disabled=True)

    item_eve_type, _ = EveType.objects.get_or_create_esi(id=EveTypeId.VELDSPAR)
    implant_eve_type, _ = EveType.objects.get_or_create_esi(
        id=EveTypeId.HIGH_GRADE_SNAKE_ALPHA
    )

    # create assets and invalid location
    asset_1 = create_character_asset(
        character=character,
        eve_type=item_eve_type,
        location=valid_location_1,
        item_id=max_location_id() + 1,
    )
    invalid_location_1 = create_location(id=asset_1.item_id)
    asset_2 = create_character_asset(
        character=character,
        eve_type=item_eve_type,
        location=valid_location_2,
        item_id=max_location_id() + 1,
    )
    invalid_location_2 = create_location(id=asset_2.item_id)

    # create character objects
    for location in [valid_location_1, invalid_location_1]:
        create_character_asset(
            character=character, eve_type=item_eve_type, location=location
        )
        jump_clone = create_character_jump_clone(character=character, location=location)
        create_character_jump_clone_implant(
            jump_clone=jump_clone, eve_type=implant_eve_type
        )
        create_character_wallet_transaction(
            character=character,
            location=location,
            eve_type=item_eve_type,
            client=corporation_entity,
        )

    create_character_location(character=character, location=invalid_location_1)
    create_character_contract_courier(
        character=character,
        assignee=None,
        issuer=character_entity,
        issuer_corporation=corporation_entity,
        start_location=valid_location_1,
        end_location=valid_location_2,
    )
    create_character_contract_courier(
        character=character,
        assignee=None,
        issuer=character_entity,
        issuer_corporation=corporation_entity,
        start_location=invalid_location_1,
        end_location=invalid_location_2,
    )
    for section in [
        Character.UpdateSection.ASSETS,
        Character.UpdateSection.CONTRACTS,
        Character.UpdateSection.LOCATION,
        Character.UpdateSection.JUMP_CLONES,
        Character.UpdateSection.WALLET_TRANSACTIONS,
    ]:
        character.update_section_log_result(
            section=section, is_success=True, is_updated=True
        )

    print("DONE!")


if __name__ == "__main__":
    main()
