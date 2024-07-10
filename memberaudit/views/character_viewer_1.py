"""Character viewer views (1/2)."""

# pylint: disable=unused-argument

from typing import Optional, Tuple

from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Count, F, Max, Q, Sum
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import format_html
from django.utils.timesince import timeuntil
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from eveuniverse.models import EveType

from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.hooks import get_extension_logger
from app_utils.helpers import humanize_number
from app_utils.logging import LoggerAddTag
from app_utils.views import (
    bootstrap_icon_plus_name_html,
    bootstrap_label_html,
    yesno_str,
)

from memberaudit import __title__
from memberaudit.constants import (
    DEFAULT_ICON_SIZE,
    MAIL_LABEL_ID_ALL_MAILS,
    MY_DATETIME_FORMAT,
    EveCategoryId,
    EveSkillTypeId,
)
from memberaudit.core.standings import Standing
from memberaudit.decorators import fetch_character_if_allowed
from memberaudit.helpers import implant_slot_num
from memberaudit.models import (
    Character,
    CharacterAsset,
    CharacterContract,
    CharacterFwStats,
    Location,
)

from ._common import add_common_context

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def item_icon_plus_name_html(item, size=DEFAULT_ICON_SIZE) -> Tuple[str, str]:
    """Return generated HTML with name and icon for asset and contract items."""
    if item.is_blueprint_copy:
        variant = item.eve_type.IconVariant.BPC
    else:
        variant = None

    name = item.name_display
    name_html = bootstrap_icon_plus_name_html(
        icon_url=item.eve_type.icon_url(size=DEFAULT_ICON_SIZE, variant=variant),
        name=name,
        size=size,
    )
    return name_html, name


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed(
    "details",
    "details__alliance",
    "details__corporation",
    "details__eve_ancestry",
    "details__eve_bloodline",
    "details__eve_bloodline__eve_race",
    "details__eve_faction",
    "details__eve_race",
    "wallet_balance",
    "skillpoints",
    "eve_character__character_ownership__user",
    "eve_character__character_ownership__user__profile__main_character",
    "eve_character",
    "location__eve_solar_system",
    "location__location",
    "location__location__eve_solar_system",
    "location__location__eve_solar_system__eve_constellation__eve_region",
    "online_status",
    "ship",
    "ship__eve_type",
    "clone_info__home_location",
    "clone_info__home_location__eve_solar_system",
)
def character_viewer(request, character_pk: int, character: Character) -> HttpResponse:
    """Main view for showing a character with all details.

    Args:
    - character_pk: PK for character to be shown
    - character: character object to be shown

    GET Params:
    - tab: ID of tab to be shown  (optional)
    """
    main, main_character_id = _mail_for_character(character)
    mailing_lists = _mailing_lists_for_character(character)
    mail_labels = _mail_labels_for_character(character, mailing_lists)
    all_characters = _identify_user_characters(request, character)
    character_assets_total = _asset_total_for_character(character)
    has_implants = character.implants.exists()
    connection_skills_differ = _connection_skills_differ_for_character(character)
    page_title = _page_title_for_character(request, character)

    context = {
        "page_title": page_title,
        "character": character,
        "auth_character": character.eve_character,
        "total_update_status": character.calc_total_update_status(),
        "character_details": character.details_or_none(),
        "mail_labels": mail_labels,
        "mailing_lists": mailing_lists,
        "main": main,
        "main_character_id": main_character_id,
        "all_characters": all_characters,
        "show_tab": request.GET.get("tab", ""),
        "sections_update_status": character.update_status_as_dict(),
        "character_assets_total": character_assets_total,
        "has_implants": has_implants,
        "connection_skills_differ": connection_skills_differ,
        "UpdateSection": Character.UpdateSection,
        "enabled_sections": Character.UpdateSection.enabled_sections(),
    }
    return render(
        request,
        "memberaudit/character_viewer.html",
        add_common_context(request, context),
    )


def _asset_total_for_character(character):
    character_assets_total = (
        character.assets.exclude(is_blueprint_copy=True)
        .aggregate(
            total=Sum(
                F("quantity") * F("eve_type__market_price__average_price"),
                output_field=models.FloatField(),
            )
        )
        .get("total")
    )

    return character_assets_total


def _mail_for_character(character):
    if character.is_orphan:
        main = "(orphan)"
        main_character_id = None
    elif character.main_character:
        main = (
            f"[{character.main_character.corporation_ticker}] "
            f"{character.main_character.character_name}"
        )
        main_character_id = character.main_character.character_id
    else:
        main = "-"
        main_character_id = None
    return main, main_character_id


def _page_title_for_character(request, character):
    page_title = _("Character Sheet")
    if not character.user_is_owner(request.user):
        page_title = format_html(
            '{}&nbsp;<i class="far fa-eye" title="{}"></i>',
            page_title,
            _("You do not own this character"),
        )

    return page_title


def _connection_skills_differ_for_character(character):
    connections_skill_level = character.skills.find_active_skill_level(
        EveSkillTypeId.CONNECTIONS
    )
    criminal_connections_skill_level = character.skills.find_active_skill_level(
        EveSkillTypeId.CRIMINAL_CONNECTIONS
    )
    connection_skills_differ = (
        connections_skill_level != criminal_connections_skill_level
    )

    return connection_skills_differ


def _mail_labels_for_character(character, mailing_lists):
    mail_labels = list(
        character.mail_labels.values(
            "label_id", "name", unread_count_2=F("unread_count")
        )
    )
    total_unread_count = sum(
        (obj["unread_count_2"] for obj in mail_labels if obj["unread_count_2"])
    )
    total_unread_count += sum(
        (obj["unread_count"] for obj in mailing_lists if obj["unread_count"])
    )
    mail_labels.append(
        {
            "label_id": MAIL_LABEL_ID_ALL_MAILS,
            "name": "All Mails",
            "unread_count_2": total_unread_count,
        }
    )

    return mail_labels


def _mailing_lists_for_character(character):
    mailing_lists_qs = character.mailing_lists.all().annotate(
        unread_count=Count("recipient_mails", filter=Q(recipient_mails__is_read=False))
    )
    mailing_lists = [
        {
            "list_id": obj.id,
            "name_plus": obj.name_plus,
            "unread_count": obj.unread_count,
        }
        for obj in mailing_lists_qs
    ]

    return mailing_lists


def _identify_user_characters(request, character):
    """Identify all characters owned by this user for sidebar."""
    if not character.user:
        eve_characters_of_user = EveCharacter.objects.none()
    else:
        eve_characters_of_user = EveCharacter.objects.select_related(
            "character_ownership__memberaudit_character"
        ).filter(character_ownership__user=character.user)
    all_characters = (
        eve_characters_of_user.order_by("character_name")
        .annotate(memberaudit_character_pk=F("memberaudit_character"))
        .annotate(is_shared=F("memberaudit_character__is_shared"))
        .values(
            "character_id", "character_name", "memberaudit_character_pk", "is_shared"
        )
    )
    accessible_characters = set(
        Character.objects.user_has_access(user=request.user).values_list(
            "pk", flat=True
        )
    )
    all_characters = [
        {
            **obj,
            **{
                "has_access": (obj["memberaudit_character_pk"] in accessible_characters)
            },
        }
        for obj in all_characters
    ]
    return all_characters


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_assets_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character assets."""

    def _combine_row(character, asset_qs, assets_with_children_ids, location_counts):
        data = []
        location_totals = {}
        for asset in asset_qs:
            if asset.location.eve_solar_system:
                region = (
                    asset.location.eve_solar_system.eve_constellation.eve_region.name
                )
                solar_system = asset.location.eve_solar_system.name
            else:
                region = ""
                solar_system = ""

            is_ship = yesno_str(
                asset.eve_type.eve_group.eve_category_id == EveCategoryId.SHIP
            )

            if asset.item_id in assets_with_children_ids:
                ajax_children_url = reverse(
                    "memberaudit:character_asset_container",
                    args=[character.pk, asset.pk],
                )
                actions_html = (
                    '<button type="button" class="btn btn-default btn-sm" '
                    'data-toggle="modal" data-target="#modalCharacterAssetContainer" '
                    f"data-ajax_children_url={ajax_children_url}>"
                    '<i class="fas fa-search"></i></button>'
                )
            else:
                actions_html = ""

            location_name = (
                f"{asset.location.name_plus} "
                f"({location_counts.get(asset.location_id, 0)})"
            )
            if location_name not in location_totals:
                location_totals[location_name] = 0.0
            if asset.total is not None:
                location_totals[location_name] += asset.total

            name_html, name = item_icon_plus_name_html(asset)
            data.append(
                {
                    "item_id": asset.item_id,
                    "location": location_name,
                    "name": {"display": name_html, "sort": name},
                    "quantity": asset.quantity if not asset.is_singleton else "",
                    "group": asset.group_display,
                    "volume": asset.eve_type.volume,
                    "price": asset.price,
                    "total": asset.total,
                    "actions": actions_html,
                    "region": region,
                    "solar_system": solar_system,
                    "is_ship": is_ship,
                }
            )

        return data, location_totals

    asset_qs = (
        character.assets.annotate_pricing()
        .select_related(
            "eve_type",
            "eve_type__eve_group",
            "eve_type__eve_group__eve_category",
            "location__eve_solar_system",
            "location__eve_solar_system__eve_constellation__eve_region",
        )
        .filter(location__isnull=False)
    )

    assets_with_children_ids = set(
        character.assets.filter(children__isnull=False).values_list(
            "item_id", flat=True
        )
    )
    location_counts = {
        obj["id"]: obj["items_count"]
        for obj in (
            Location.objects.select_related("characterasset__character")
            .filter(characterasset__character=character)
            .annotate(items_count=Count("characterasset"))
            .values("id", "items_count")
        )
    }
    data, location_totals = _combine_row(
        character, asset_qs, assets_with_children_ids, location_counts
    )
    for row in data:
        sum_str = humanize_number(location_totals[row["location"]])
        row["location"] = row["location"] + f" ({sum_str} ISK)"

    return JsonResponse({"data": data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_asset_container(
    request, character_pk: int, character: Character, parent_asset_pk: int
) -> HttpResponse:
    """Render view for character asset container."""
    try:
        parent_asset = character.assets.select_related(
            "location", "eve_type", "eve_type__eve_group"
        ).get(pk=parent_asset_pk)
    except CharacterAsset.DoesNotExist:
        error_msg = (
            f"Asset with pk {parent_asset_pk} not found for character {character}"
        )
        logger.warning(error_msg)
        context = {
            "error": error_msg,
        }
    else:
        context = {
            "character": character,
            "parent_asset": parent_asset,
            "parent_asset_icon_url": parent_asset.eve_type.icon_url(
                size=DEFAULT_ICON_SIZE
            ),
        }
    return render(
        request,
        "memberaudit/modals/character_viewer/asset_container_content.html",
        context,
    )


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_asset_container_data(
    request, character_pk: int, character: Character, parent_asset_pk: int
) -> JsonResponse:
    """Render data view for character asset container."""
    data = []
    try:
        parent_asset = character.assets.get(pk=parent_asset_pk)
    except CharacterAsset.DoesNotExist:
        error_msg = (
            f"Asset with pk {parent_asset_pk} not found for character {character}"
        )
        logger.warning(error_msg)
        return HttpResponseNotFound(error_msg)

    try:
        assets_qs = parent_asset.children.annotate_pricing().select_related(
            "eve_type",
            "eve_type__eve_group",
            "eve_type__eve_group__eve_category",
        )
    except ObjectDoesNotExist:
        return HttpResponseNotFound()

    for asset in assets_qs:
        name_html, name = item_icon_plus_name_html(asset)
        data.append(
            {
                "item_id": asset.item_id,
                "name": {"display": name_html, "sort": name},
                "quantity": asset.quantity if not asset.is_singleton else "",
                "group": asset.group_display,
                "volume": asset.eve_type.volume,
                "price": asset.price,
                "total": asset.total,
            }
        )
    return JsonResponse({"data": data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_attribute_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character attributes."""
    try:
        character_attributes = character.attributes
    except ObjectDoesNotExist:
        character_attributes = None

    context = {"character_attributes": character_attributes}

    return render(
        request,
        "memberaudit/partials/character_viewer/tabs/character_attributes_content.html",
        context,
    )


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_contacts_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character contacts."""
    data = []
    for contact in character.contacts.select_related("eve_entity").all():
        eve_entity = contact.eve_entity
        name = eve_entity.name
        if not name:
            continue

        is_npc = eve_entity.is_npc
        if is_npc:
            name_plus = format_html("{} {}", name, bootstrap_label_html("NPC", "info"))
        else:
            name_plus = name

        name_html = bootstrap_icon_plus_name_html(
            eve_entity.icon_url(DEFAULT_ICON_SIZE), name_plus, avatar=True
        )
        standing = Standing.from_value(contact.standing)
        is_watched = contact.is_watched is True
        is_blocked = contact.is_blocked is True
        category_name = eve_entity.get_category_display().title()

        data.append(
            {
                "id": contact.eve_entity_id,
                "name": {"display": name_html, "sort": name},
                "standing": contact.standing,
                "type": category_name,
                "is_watched": is_watched,
                "is_blocked": is_blocked,
                "is_watched_str": yesno_str(is_watched),
                "is_blocked_str": yesno_str(is_blocked),
                "is_npc_str": yesno_str(is_npc),
                "group_name": standing.label.title(),
                "group_sort": standing.value,
            }
        )

    return JsonResponse({"data": data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_contracts_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character contracts."""
    data = []
    for contract in character.contracts.select_related("issuer", "assignee").all():
        if now() < contract.date_expired:
            time_left = timeuntil(contract.date_expired, now())
        else:
            time_left = "expired"

        ajax_contract_detail = reverse(
            "memberaudit:character_contract_details",
            args=[character.pk, contract.pk],
        )

        actions_html = (
            '<button type="button" class="btn btn-primary" '
            'data-toggle="modal" data-target="#modalCharacterContract" '
            f"data-ajax_contract_detail={ajax_contract_detail}>"
            '<i class="fas fa-search"></i></button>'
        )
        data.append(
            {
                "contract_id": contract.contract_id,
                "summary": contract.summary(),
                "type": contract.get_contract_type_display().title(),
                "from": contract.issuer.name,
                "to": contract.assignee.name if contract.assignee else "(None)",
                "status": contract.get_status_display(),
                "date_issued": contract.date_issued.isoformat(),
                "time_left": time_left,
                "info": contract.title,
                "actions": actions_html,
            }
        )

    return JsonResponse({"data": data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_contract_details(
    request, character_pk: int, character: Character, contract_pk: int
) -> HttpResponse:
    """Render view for character contract details."""
    error_msg = None
    try:
        contract = (
            character.contracts.select_related(
                "issuer", "start_location", "end_location", "assignee"
            )
            .prefetch_related("bids")
            .get(pk=contract_pk)
        )
    except CharacterContract.DoesNotExist:
        error_msg = (
            f"Contract with pk {contract_pk} not found for character {character}"
        )
        logger.warning(error_msg)
        context = {
            "error": error_msg,
            "character": character,
        }
    else:
        has_items_included = contract.items.filter(is_included=True).exists()
        has_items_requested = contract.items.filter(is_included=False).exists()
        current_bid = contract.bids.all().aggregate(Max("amount")).get("amount__max")
        bids_count = contract.bids.count()
        context = {
            "character": character,
            "contract": contract,
            "contract_summary": contract.summary(),
            "MY_DATETIME_FORMAT": MY_DATETIME_FORMAT,
            "has_items_included": has_items_included,
            "has_items_requested": has_items_requested,
            "current_bid": current_bid,
            "bids_count": bids_count,
        }
    return render(
        request,
        "memberaudit/modals/character_viewer/contract_content.html",
        add_common_context(request, context),
    )


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_contract_items_included_data(
    request, character_pk: int, character: Character, contract_pk: int
) -> JsonResponse:
    """Render data view for included character contract items."""
    return _character_contract_items_data(
        request=request,
        character_pk=character_pk,
        character=character,
        contract_pk=contract_pk,
        is_included=True,
    )


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_contract_items_requested_data(
    request, character_pk: int, character: Character, contract_pk: int
) -> JsonResponse:
    """Render data view for requested character contract items."""
    return _character_contract_items_data(
        request=request,
        character_pk=character_pk,
        character=character,
        contract_pk=contract_pk,
        is_included=False,
    )


def _character_contract_items_data(
    request,
    character_pk: int,
    character: Character,
    contract_pk: int,
    is_included: bool,
) -> JsonResponse:
    data = []
    try:
        contract = character.contracts.prefetch_related("items").get(pk=contract_pk)
    except CharacterAsset.DoesNotExist:
        error_msg = (
            f"Contract with pk {contract_pk} not found for character {character}"
        )
        logger.warning(error_msg)
        return HttpResponseNotFound(error_msg)

    items_qs = (
        contract.items.annotate_pricing()
        .filter(is_included=is_included)
        .select_related(
            "eve_type", "eve_type__eve_group", "eve_type__eve_group__eve_category"
        )
    )

    for item in items_qs:
        name_html, name = item_icon_plus_name_html(item)
        data.append(
            {
                "id": item.record_id,
                "name": {
                    "display": name_html,
                    "sort": name,
                },
                "quantity": item.quantity if not item.is_singleton else "",
                "group": item.eve_type.eve_group.name,
                "category": item.eve_type.eve_group.eve_category.name,
                "price": item.price,
                "total": item.total,
                "is_blueprint_copy": item.is_blueprint_copy,
            }
        )

    return JsonResponse({"data": data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_corporation_history(
    request, character_pk: int, character: Character
) -> HttpResponse:
    """Render view for character corporation history."""
    corporation_history = []
    try:
        corporation_history_qs = character.corporation_history.select_related(
            "corporation"
        ).order_by("start_date")
    except ObjectDoesNotExist:
        pass

    else:
        for entry in corporation_history_qs:
            if len(corporation_history) > 0:
                corporation_history[-1]["end_date"] = entry.start_date
                corporation_history[-1]["is_last"] = False

            corporation_history.append(
                {
                    "id": entry.pk,
                    "corporation_name": entry.corporation.name,
                    "start_date": entry.start_date,
                    "end_date": now(),
                    "is_last": True,
                    "is_deleted": entry.is_deleted,
                }
            )

    context = {
        "corporation_history": reversed(corporation_history),
        "has_corporation_history": len(corporation_history) > 0,
    }
    return render(
        request,
        "memberaudit/partials/character_viewer/tabs/corporation_history_2.html",
        add_common_context(request, context),
    )


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_fw_stats(
    request, character_pk: int, character: Character
) -> HttpResponse:
    """Render view for character FW stats."""
    try:
        fw_stats: Optional[CharacterFwStats] = character.fw_stats
    except ObjectDoesNotExist:
        fw_stats = None
    if fw_stats:
        logo_url = fw_stats.faction.logo_url(128) if fw_stats.faction else ""
    else:
        logo_url = ""
    context = {"fw_stats": fw_stats, "faction_logo_url": logo_url}
    return render(
        request,
        "memberaudit/partials/character_viewer/tabs/fw_stats_content.html",
        context,
    )


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_implants_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character implants."""
    data = []
    for implant in character.implants.select_related("eve_type").prefetch_related(
        "eve_type__dogma_attributes"
    ):
        implant_html = bootstrap_icon_plus_name_html(
            implant.eve_type.icon_url(
                DEFAULT_ICON_SIZE, variant=EveType.IconVariant.REGULAR
            ),
            implant.eve_type.name,
        )
        slot_num = implant_slot_num(implant.eve_type)
        data.append(
            {
                "id": implant.pk,
                "implant": {"display": implant_html, "sort": slot_num},
            }
        )

    return JsonResponse({"data": data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_loyalty_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character loyalty points."""
    data = []
    for entry in character.loyalty_entries.select_related("corporation"):
        corporation_html = bootstrap_icon_plus_name_html(
            entry.corporation.icon_url(DEFAULT_ICON_SIZE), entry.corporation.name
        )
        data.append(
            {
                "id": entry.pk,
                "corporation": {
                    "display": corporation_html,
                    "sort": entry.corporation.name,
                },
                "loyalty_points": entry.loyalty_points,
            }
        )

    return JsonResponse({"data": data})
