"""Character viewer views (2/2)."""

# pylint: disable=unused-argument

import datetime as dt
from collections import defaultdict
from typing import Optional

import humanize

from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from eveuniverse.core import eveimageserver
from eveuniverse.models import EveType

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag
from app_utils.views import (
    bootstrap_icon_plus_name_html,
    bootstrap_label_html,
    link_html,
    no_wrap_html,
    yesno_str,
)

from memberaudit import __title__
from memberaudit.constants import (
    DATETIME_FORMAT,
    DEFAULT_ICON_SIZE,
    MAIL_LABEL_ID_ALL_MAILS,
    MY_DATETIME_FORMAT,
    SKILL_SET_DEFAULT_ICON_TYPE_ID,
    EveSkillTypeId,
)
from memberaudit.core.standings import Standing
from memberaudit.decorators import fetch_character_if_allowed
from memberaudit.helpers import arabic_number_to_roman, implant_slot_num
from memberaudit.models import (
    Character,
    CharacterMail,
    CharacterPlanet,
    CharacterRole,
    CharacterStanding,
    SkillSet,
    SkillSetSkill,
)

from ._common import UNGROUPED_SKILL_SET, eve_solar_system_to_html

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

ICON_SIZE_64 = 64
CHARACTER_VIEWER_DEFAULT_TAB = "mails"

ICON_FAILED = "fas fa-times boolean-icon-false"
ICON_PARTIAL = "fas fa-check text-warning"
ICON_FULL = "fas fa-check-double text-success"
ICON_MET_ALL_REQUIRED = "fas fa-check text-success"


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_jump_clones_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Return data for character jump clones."""
    data = []
    try:
        for jump_clone in (
            character.jump_clones.select_related(
                "location",
                "location__eve_solar_system",
                "location__eve_solar_system__eve_constellation__eve_region",
            )
            .prefetch_related("implants", "implants__eve_type__dogma_attributes")
            .all()
        ):
            if (
                not jump_clone.location.is_empty
                and not jump_clone.location.is_unknown_location
            ):
                eve_solar_system = jump_clone.location.eve_solar_system
                solar_system = eve_solar_system_to_html(
                    eve_solar_system, show_region=False
                )
                region = eve_solar_system.eve_constellation.eve_region.name
            else:
                solar_system = "-"
                region = "-"

            implants_data = []
            for implant in jump_clone.implants.all():
                slot_num = implant_slot_num(implant.eve_type)
                implants_data.append(
                    {
                        "name": implant.eve_type.name,
                        "icon_url": implant.eve_type.icon_url(
                            DEFAULT_ICON_SIZE, variant=EveType.IconVariant.REGULAR
                        ),
                        "slot_num": slot_num,
                    }
                )
            if implants_data:
                implants = "<br>".join(
                    bootstrap_icon_plus_name_html(
                        implant["icon_url"], no_wrap_html(implant["name"]), size=24
                    )
                    for implant in sorted(implants_data, key=lambda k: k["slot_num"])
                )
            else:
                implants = "(none)"

            data.append(
                {
                    "id": jump_clone.pk,
                    "region": region,
                    "solar_system": solar_system,
                    "location": jump_clone.location.name_plus,
                    "implants": implants,
                }
            )
    except ObjectDoesNotExist:
        pass

    return JsonResponse({"data": data})


def _character_mail_headers_data(request, character, mail_headers_qs) -> JsonResponse:
    mails_data = []
    try:
        for mail in mail_headers_qs.select_related("sender").prefetch_related(
            "recipients"
        ):
            mail_ajax_url = reverse(
                "memberaudit:character_mail", args=[character.pk, mail.pk]
            )
            if mail.body:
                actions_html = (
                    '<button type="button" class="btn btn-primary" '
                    'data-toggle="modal" data-target="#modalCharacterMail" '
                    f"data-ajax_url={mail_ajax_url}>"
                    '<i class="fas fa-search"></i></button>'
                )
            else:
                actions_html = ""

            mails_data.append(
                {
                    "mail_id": mail.mail_id,
                    "from": mail.sender.name_plus,
                    "to": ", ".join(
                        sorted([obj.name_plus for obj in mail.recipients.all()])
                    ),
                    "subject": mail.subject,
                    "sent": mail.timestamp.isoformat(),
                    "action": actions_html,
                    "is_read": mail.is_read,
                    "is_unread_str": yesno_str(mail.is_read is False),
                }
            )
    except ObjectDoesNotExist:
        pass

    return JsonResponse({"data": mails_data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_mail_headers_by_label_data(
    request, character_pk: int, character: Character, label_id: int
) -> JsonResponse:
    """Return data for character mail headers by label."""
    if label_id == MAIL_LABEL_ID_ALL_MAILS:
        mail_headers_qs = character.mails.all()
    else:
        mail_headers_qs = character.mails.filter(labels__label_id=label_id)

    return _character_mail_headers_data(request, character, mail_headers_qs)


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_mail_headers_by_list_data(
    request, character_pk: int, character: Character, list_id: int
) -> JsonResponse:
    """Render data view for character mail headers by list."""
    mail_headers_qs = character.mails.filter(recipients__id=list_id)
    return _character_mail_headers_data(request, character, mail_headers_qs)


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_mail(
    request, character_pk: int, character: Character, mail_pk: int
) -> HttpResponse:
    """Render character mail view."""
    try:
        mail = (
            character.mails.select_related("sender")
            .prefetch_related("recipients")
            .get(pk=mail_pk)
        )
    except CharacterMail.DoesNotExist:
        error_msg = _("Mail with pk %s not found for character %s") % (
            mail_pk,
            character,
        )
        logger.warning(error_msg)
        return HttpResponseNotFound(error_msg)

    recipients = sorted(
        [
            {
                "name": obj.name_plus,
                "link": link_html(obj.external_url(), obj.name_plus),
            }
            for obj in mail.recipients.all()
        ],
        key=lambda k: k["name"],
    )
    context = {
        "mail_id": mail.mail_id,
        "labels": list(mail.labels.values_list("label_id", flat=True)),
        "sender": link_html(mail.sender.external_url(), mail.sender.name_plus),
        "recipients": format_html(", ".join([obj["link"] for obj in recipients])),
        "subject": mail.subject,
        "timestamp": mail.timestamp,
        "body": mail.body_html if mail.body else None,
        "MY_DATETIME_FORMAT": MY_DATETIME_FORMAT,
    }
    return render(
        request, "memberaudit/modals/character_viewer/mail_content.html", context
    )


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_mining_ledger_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character mining ledger."""
    qs = character.mining_ledger.select_related(
        "eve_solar_system",
        "eve_solar_system__eve_constellation__eve_region",
        "eve_type",
    ).annotate_pricing()
    data = [
        {
            "date": row.date.isoformat(),
            "quantity": row.quantity,
            "region": row.eve_solar_system.eve_constellation.eve_region.name,
            "solar_system": row.eve_solar_system.name,
            "price": row.price,
            "total": row.total,
            "type": row.eve_type.name,
        }
        for row in qs
    ]
    return JsonResponse({"data": data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_planets_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character planets."""
    data = []
    for planet in character.planets.select_related(
        "eve_planet",
        "eve_planet__eve_type",
        "eve_planet__eve_solar_system",
        "eve_planet__eve_solar_system__eve_constellation__eve_region",
    ):
        planet: CharacterPlanet
        eve_solar_system = planet.eve_planet.eve_solar_system
        solar_system_html = eve_solar_system_to_html(
            eve_solar_system, show_region=False
        )
        last_update_html = format_html(
            '<span title="{}">{}</span>',
            planet.last_update_at.strftime(DATETIME_FORMAT),
            humanize.naturaltime(planet.last_update_at),
        )
        upgrade_level = (
            arabic_number_to_roman(planet.upgrade_level) if planet.upgrade_level else ""
        )
        data.append(
            {
                "id": planet.pk,
                "last_update": {
                    "display": last_update_html,
                    "sort": planet.last_update_at.isoformat(),
                },
                "num_pins": planet.num_pins,
                "region": eve_solar_system.eve_constellation.eve_region.name,
                "planet": planet.eve_planet.name,
                "solar_system": {
                    "display": solar_system_html,
                    "sort": eve_solar_system.name,
                },
                "solar_system_name": eve_solar_system.name,
                "type": planet.eve_planet.type_name(),
                "upgrade_level": upgrade_level,
            }
        )

    return JsonResponse({"data": data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_roles_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character roles."""
    character_roles_map = defaultdict(set)
    for obj in character.roles.all():
        location = CharacterRole.Location(obj.location)
        role = CharacterRole.Role(obj.role)
        character_roles_map[location].add(role)

    data = []
    if character_roles_map:
        for roles_group in CharacterRole.ROLES_GROUPED:
            location = roles_group["location"]
            group_name = roles_group["title"].title()

            for role in roles_group["roles"]:
                has_role = role in character_roles_map.get(location, [])
                data.append(
                    {
                        "group": group_name,
                        "role": role.label.title(),
                        "has_role": has_role,
                    }
                )

    return JsonResponse({"data": data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_skillqueue_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character skillqueue."""
    data = []
    try:
        for row in character.skillqueue.select_related("eve_type").filter(
            character_id=character_pk
        ):
            level_roman = arabic_number_to_roman(row.finished_level)
            skill_str = f"{row.eve_type.name}&nbsp;{level_roman}"
            if row.is_active:
                skill_str += " [ACTIVE]"

            if row.finish_date:
                finish_date_humanized = humanize.naturaltime(
                    dt.datetime.now()
                    + dt.timedelta(
                        seconds=(
                            row.finish_date.timestamp() - dt.datetime.now().timestamp()
                        )
                    )
                )
                finish_date_str = (
                    f"{row.finish_date.strftime(DATETIME_FORMAT)} "
                    f"({finish_date_humanized})"
                )
                finish_date_sort = row.finish_date.isoformat()
            else:
                finish_date_str = gettext("(training not active)")
                finish_date_sort = None

            data.append(
                {
                    "position": row.queue_position + 1,
                    "skill": skill_str,
                    "finished": {
                        "display": finish_date_str,
                        "sort": finish_date_sort,
                    },
                    "is_active": row.is_active,
                }
            )
    except ObjectDoesNotExist:
        pass

    return JsonResponse({"data": data})


@login_required
@permission_required(["memberaudit.basic_access", "memberaudit.view_skill_sets"])
@fetch_character_if_allowed()
def character_skill_sets_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character skill sets."""

    def _create_row(skill_check):
        def _skill_set_name_html(skill_set):
            url = (
                skill_set.ship_type.icon_url(
                    DEFAULT_ICON_SIZE, variant=EveType.IconVariant.REGULAR
                )
                if skill_set.ship_type
                else eveimageserver.type_icon_url(
                    SKILL_SET_DEFAULT_ICON_TYPE_ID, size=DEFAULT_ICON_SIZE
                )
            )
            ship_icon = f'<img width="24" heigh="24" src="{url}"/>'
            return ship_icon + "&nbsp;&nbsp;" + skill_set.name

        def _group_name(group):
            if group:
                return (
                    group.name_plus if group.is_active else group.name + " [Not active]"
                )
            return UNGROUPED_SKILL_SET

        def _compile_failed_skills(skill_set_skills, level_name) -> Optional[list]:
            skills2 = sorted(
                [
                    {
                        "name": obj.eve_type.name,
                        "required_level": obj.required_level,
                        "recommended_level": obj.recommended_level,
                    }
                    for obj in skill_set_skills
                ],
                key=lambda k: k["name"].lower(),
            )
            return [
                bootstrap_label_html(
                    format_html(
                        "{}&nbsp;{}",
                        obj["name"],
                        arabic_number_to_roman(obj[level_name]),
                    ),
                    "default",
                )
                for obj in skills2
            ]

        def _format_failed_skills(skills) -> str:
            return " ".join(skills) if skills else "-"

        failed_required_skills = list(skill_check.failed_required_skills_prefetched)
        has_required = not bool(failed_required_skills)
        failed_required_skills_str = _format_failed_skills(
            _compile_failed_skills(failed_required_skills, "required_level")
        )
        failed_recommended_skills = list(
            skill_check.failed_recommended_skills_prefetched
        )
        has_recommended = not bool(failed_recommended_skills)
        failed_recommended_skills_str = _format_failed_skills(
            _compile_failed_skills(failed_recommended_skills, "recommended_level")
        )
        is_doctrine = group.is_doctrine if group else False
        ajax_children_url = reverse(
            "memberaudit:character_skill_set_details",
            args=[character.pk, skill_check.skill_set_id],
        )
        actions_html = (
            '<button type="button" class="btn btn-primary" '
            'data-toggle="modal" data-target="#modalCharacterSkillSetDetails" '
            f"data-ajax_skill_set_detail={ ajax_children_url }>"
            '<i class="fas fa-search"></i></button>'
        )
        return {
            "id": skill_check.id,
            "group": _group_name(group),
            "skill_set": _skill_set_name_html(skill_check.skill_set),
            "skill_set_name": skill_set.name,
            "is_doctrine_str": yesno_str(is_doctrine),
            "failed_required_skills": failed_required_skills_str,
            "has_required": has_required,
            "has_required_str": yesno_str(has_required),
            "failed_recommended_skills": failed_recommended_skills_str,
            "has_recommended": has_recommended,
            "has_recommended_str": yesno_str(has_recommended),
            "action": actions_html,
        }

    groups_map = SkillSet.objects.compile_groups_map()
    skill_checks_qs = (
        character.skill_set_checks.select_related("skill_set", "skill_set__ship_type")
        .prefetch_related(
            Prefetch(
                "failed_required_skills",
                queryset=SkillSetSkill.objects.select_related("eve_type"),
                to_attr="failed_required_skills_prefetched",
            )
        )
        .prefetch_related(
            Prefetch(
                "failed_recommended_skills",
                queryset=SkillSetSkill.objects.select_related("eve_type"),
                to_attr="failed_recommended_skills_prefetched",
            )
        )
        .all()
    )
    skill_checks = {obj.skill_set_id: obj for obj in skill_checks_qs}
    data = []
    for group_map in groups_map.values():
        group = group_map["group"]
        for skill_set in group_map["skill_sets"]:
            try:
                skill_check = skill_checks[skill_set.id]
            except KeyError:
                continue
            else:
                row = _create_row(skill_check)
                data.append(row)
    data = sorted(data, key=lambda k: (k["group"].lower(), k["skill_set_name"].lower()))
    return JsonResponse({"data": data})


@login_required
@permission_required(["memberaudit.basic_access", "memberaudit.view_skill_sets"])
@fetch_character_if_allowed()
def character_skill_set_details(
    request, character_pk: int, character: Character, skill_set_pk: int
) -> HttpResponse:
    """Render view for character skill set details."""

    def _compile_row(character_skills, missing_skills, skill_id, skill):
        character_skill = character_skills.get(skill_id)
        recommended_level_str = "-"
        required_level_str = "-"
        current_str = "-"
        result_icon = ICON_FAILED
        met_required = True

        if character_skill:
            current_str = arabic_number_to_roman(character_skill.active_skill_level)

        if skill.recommended_level:
            recommended_level_str = arabic_number_to_roman(skill.recommended_level)

        if skill.required_level:
            required_level_str = arabic_number_to_roman(skill.required_level)

        if not character_skill:
            result_icon = ICON_FAILED
            met_required = False
        else:
            if (
                skill.required_level
                and not skill.recommended_level
                and character_skill.active_skill_level >= skill.required_level
            ):
                result_icon = ICON_FULL
            elif (
                skill.recommended_level
                and character_skill.active_skill_level >= skill.recommended_level
            ):
                result_icon = ICON_FULL
            elif (
                skill.required_level
                and character_skill.active_skill_level >= skill.required_level
            ):
                result_icon = ICON_PARTIAL
            else:
                met_required = False

        if not character_skill or (
            character_skill and character_skill.active_skill_level < skill.maximum_level
        ):
            missing_skills.append(skill.maximum_skill_str)

        return {
            "name": skill.eve_type.name,
            "required": required_level_str,
            "recommended": recommended_level_str,
            "current": current_str,
            "result_icon": result_icon,
            "met_required": met_required,
        }

    skill_set = get_object_or_404(SkillSet, pk=skill_set_pk)
    skill_set_skills = _calc_skill_set_skills(skill_set_pk)
    character_skills = _calc_character_skills(character, skill_set_skills)
    out_data = []
    missing_skills = []
    for skill_id, skill in skill_set_skills.items():
        out_data.append(_compile_row(character_skills, missing_skills, skill_id, skill))

    met_all_required = True
    for data in out_data:
        if not data["met_required"]:
            met_all_required = False
            break

    context = {
        "name": skill_set.name,
        "description": skill_set.description,
        "ship_url": _calc_url_for_skill_set(skill_set),
        "skills": sorted(out_data, key=lambda k: (k["name"].lower())),
        "met_all_required": met_all_required,
        "icon_failed": ICON_FAILED,
        "icon_partial": ICON_PARTIAL,
        "icon_full": ICON_FULL,
        "icon_met_all_required": ICON_MET_ALL_REQUIRED,
        "missing_skills_str": "\n".join(missing_skills) if missing_skills else "",
    }

    return render(
        request,
        "memberaudit/modals/character_viewer/skill_set_content.html",
        context,
    )


def _calc_url_for_skill_set(skill_set):
    url = (
        skill_set.ship_type.icon_url(ICON_SIZE_64, variant=EveType.IconVariant.REGULAR)
        if skill_set.ship_type
        else eveimageserver.type_icon_url(
            SKILL_SET_DEFAULT_ICON_TYPE_ID, size=ICON_SIZE_64
        )
    )

    return url


def _calc_skill_set_skills(skill_set_pk):
    skill_set_skills_qs = SkillSetSkill.objects.select_related("eve_type").filter(
        skill_set_id=skill_set_pk
    )
    skill_set_skills = {obj.eve_type_id: obj for obj in skill_set_skills_qs}
    return skill_set_skills


def _calc_character_skills(character, skill_set_skills):
    character_skills_qs = character.skills.select_related("eve_type").filter(
        eve_type_id__in=skill_set_skills.keys()
    )
    character_skills = {obj.eve_type_id: obj for obj in character_skills_qs}
    return character_skills


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_skills_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character skills."""
    skills_data = []
    try:
        for skill in character.skills.select_related("eve_type", "eve_type__eve_group"):
            level_str = arabic_number_to_roman(skill.active_skill_level)
            skill_name = format_html(
                '<span title="{}">{} {}</span>',
                skill.eve_type.description,
                skill.eve_type.name,
                level_str,
            )
            skills_data.append(
                {
                    "group": skill.eve_type.eve_group.name,
                    "skill": skill.eve_type.name,
                    "skill_name": skill_name,
                    "level": skill.active_skill_level,
                    "level_str": level_str,
                }
            )
    except ObjectDoesNotExist:
        pass

    return JsonResponse({"data": skills_data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_standings_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character standings."""
    connections_skill_level = character.skills.find_active_skill_level(
        EveSkillTypeId.CONNECTIONS
    )
    diplomacy_skill_level = character.skills.find_active_skill_level(
        EveSkillTypeId.DIPLOMACY
    )
    criminal_connections_skill_level = character.skills.find_active_skill_level(
        EveSkillTypeId.CRIMINAL_CONNECTIONS
    )
    data = []
    for obj in character.standings.select_related("eve_entity").all():
        obj: CharacterStanding
        name = obj.eve_entity.name
        name_html = bootstrap_icon_plus_name_html(
            obj.eve_entity.icon_url(DEFAULT_ICON_SIZE), name, avatar=True
        )
        map_category = {
            "character": _("Agent"),
            "corporation": _("Corporation"),
            "faction": _("Faction"),
        }
        npc_type = map_category.get(obj.eve_entity.get_category_display(), "")
        effective_standing = obj.effective_standing(
            connections_skill_level=connections_skill_level,
            criminal_connections_skill_level=criminal_connections_skill_level,
            diplomacy_skill_level=diplomacy_skill_level,
        )
        standing_str = f"{effective_standing:.2f} ({obj.standing:.2f})"
        standing_group = Standing.from_value(effective_standing)
        data.append(
            {
                "id": obj.eve_entity.id,
                "group_name": standing_group.label.title(),
                "group_sort": standing_group.value,
                "name": {"display": name_html, "sort": name},
                "standing": {"display": standing_str, "sort": effective_standing},
                "type": npc_type,
            }
        )

    return JsonResponse({"data": data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_titles_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character titles."""
    data = [
        {"id": title.title_id, "name": title.name}
        for title in character.titles.order_by("title_id")
    ]
    return JsonResponse({"data": data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_wallet_journal_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character wallet journal."""
    wallet_data = []
    try:
        for row in character.wallet_journal.select_related(
            "first_party", "second_party"
        ).all():
            first_party = row.first_party.name if row.first_party else "-"
            second_party = row.second_party.name if row.second_party else "-"
            wallet_data.append(
                {
                    "date": row.date.isoformat(),
                    "ref_type": row.ref_type.replace("_", " ").title(),
                    "first_party": first_party,
                    "second_party": second_party,
                    "amount": float(row.amount),
                    "balance": float(row.balance),
                    "description": row.description,
                    "reason": row.reason,
                }
            )
    except ObjectDoesNotExist:
        pass

    return JsonResponse({"data": wallet_data})


@login_required
@permission_required("memberaudit.basic_access")
@fetch_character_if_allowed()
def character_wallet_transactions_data(
    request, character_pk: int, character: Character
) -> JsonResponse:
    """Render data view for character wallet transactions."""
    wallet_data = []
    try:
        for row in character.wallet_transactions.select_related(
            "client", "eve_type", "location"
        ).all():
            buy_or_sell = _("Buy") if row.is_buy else _("Sell")
            wallet_data.append(
                {
                    "date": row.date.isoformat(),
                    "quantity": row.quantity,
                    "type": row.eve_type.name,
                    "unit_price": float(row.unit_price),
                    "total": float(
                        row.unit_price * row.quantity * (-1 if row.is_buy else 1)
                    ),
                    "client": row.client.name,
                    "location": row.location.name,
                    "is_buy": row.is_buy,
                    "buy_or_sell": buy_or_sell,
                }
            )
    except ObjectDoesNotExist:
        pass
    return JsonResponse({"data": wallet_data})
