"""Report views."""

from typing import Any

from datatables.views import DataTableView

from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from eveuniverse.core import eveimageserver
from eveuniverse.models import EveType

from allianceauth.authentication.models import get_guest_state_pk
from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag
from app_utils.views import bootstrap_icon_plus_name_html, yesno_str

from memberaudit import __title__
from memberaudit.constants import DEFAULT_ICON_SIZE, SKILL_SET_DEFAULT_ICON_TYPE_ID
from memberaudit.models import Character, CharacterSkillSetCheck, General, SkillSetGroup

from ._common import add_common_context

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def create_organization_html(eve_character: EveCharacter) -> str:
    """Return character's organization as HTML."""
    return format_html(
        "{}{}",
        eve_character.corporation_name,
        f" [{eve_character.alliance_ticker}]" if eve_character.alliance_name else "",
    )


@login_required
@permission_required("memberaudit.reports_access")
def reports(request) -> HttpResponse:
    """Render view for reports."""
    context = {"page_title": _("Reports")}
    return render(
        request, "memberaudit/reports.html", add_common_context(request, context)
    )


@login_required
@permission_required("memberaudit.reports_access")
def user_compliance_report_data(request) -> JsonResponse:
    """Render data view for user compliance report."""
    users_and_character_counts = (
        General.accessible_users(request.user)
        .exclude(profile__state__pk=get_guest_state_pk())
        .annotate(total_chars=Count("character_ownerships__character", distinct=True))
        .annotate(
            unregistered_chars=Count(
                "character_ownerships",
                filter=Q(character_ownerships__character__memberaudit_character=None),
                distinct=True,
            )
        )
        .select_related(
            "profile__main_character",
            "profile__state",
            "profile__main_character__memberaudit_character",
        )
    )
    user_data = []
    for user in users_and_character_counts:
        if user.profile.main_character:
            main_character = user.profile.main_character
            if user == request.user or request.user.has_perm(
                "memberaudit.characters_access"
            ):
                try:
                    character = main_character.memberaudit_character
                except ObjectDoesNotExist:
                    url = None
                else:
                    url = reverse("memberaudit:character_viewer", args=[character.pk])
            else:
                url = None
            main_name = main_character.character_name
            main_html = bootstrap_icon_plus_name_html(
                main_character.portrait_url(),
                main_character.character_name,
                avatar=True,
                url=url,
            )
            corporation_name = main_character.corporation_name
            organization_html = create_organization_html(main_character)
            alliance_name = (
                main_character.alliance_name if main_character.alliance_name else ""
            )
            is_compliant = user.unregistered_chars == 0
        else:
            main_name = user.username
            main_html = bootstrap_icon_plus_name_html(
                eveimageserver.character_portrait_url(1, size=DEFAULT_ICON_SIZE),
                main_name,
                avatar=True,
                url=url,
            )
            alliance_name = organization_html = corporation_name = ""
            is_compliant = False

        is_registered = user.unregistered_chars < user.total_chars
        user_data.append(
            {
                "id": user.pk,
                "main": {
                    "display": main_html,
                    "sort": main_name,
                },
                "organization": {
                    "display": organization_html,
                    "sort": corporation_name,
                },
                "state": user.profile.state.name,
                "corporation_name": corporation_name,
                "alliance_name": alliance_name,
                "total_chars": user.total_chars,
                "unregistered_chars": user.unregistered_chars,
                "is_registered": is_registered,
                "registered_str": yesno_str(is_registered),
                "is_compliant": is_compliant,
                "compliance_str": yesno_str(is_compliant),
            }
        )
    return JsonResponse({"data": user_data})


@login_required
@permission_required("memberaudit.reports_access")
def corporation_compliance_report_data(request) -> JsonResponse:
    """Render data view for corporation compliance report."""
    relevant_user_ids = list(
        General.accessible_users(request.user)
        .exclude(profile__state__pk=get_guest_state_pk())
        .values_list("id", flat=True)
    )
    corporations = (
        EveCharacter.objects.select_related(
            "userprofile",
            "userprofile__user__character_ownerships__character",
            "userprofile__user__character_ownerships",
        )
        .filter(userprofile__in=relevant_user_ids)
        .values(
            "corporation_id",
            "corporation_name",
            "alliance_id",
            "alliance_name",
            "alliance_ticker",
        )
        .distinct()
        .annotate(mains_count=Count("userprofile", distinct=True))
        .annotate(
            characters_count=Count(
                "userprofile__user__character_ownerships__character", distinct=True
            )
        )
        .annotate(
            unregistered_count=Count(
                "userprofile__user__character_ownerships",
                filter=Q(
                    userprofile__user__character_ownerships__character__memberaudit_character__isnull=True
                ),
                distinct=True,
            )
        )
    )
    data = []
    for corporation in corporations:
        corporation_name = corporation["corporation_name"]
        alliance_ticker = (
            f" [{corporation['alliance_ticker']}]"
            if corporation["alliance_ticker"]
            else ""
        )
        organization_name = f"{corporation_name}{alliance_ticker}"
        alliance_name = (
            corporation["alliance_name"] if corporation["alliance_name"] else ""
        )
        compliance_p = (
            round(
                (corporation["characters_count"] - corporation["unregistered_count"])
                / corporation["characters_count"]
                * 100
            )
            if corporation["characters_count"] > 0
            else 0
        )
        is_compliant = compliance_p == 100
        data.append(
            {
                "id": corporation["corporation_id"],
                "organization_html": {
                    "display": bootstrap_icon_plus_name_html(
                        icon_url=eveimageserver.corporation_logo_url(
                            corporation_id=corporation["corporation_id"],
                            size=DEFAULT_ICON_SIZE,
                        ),
                        name=organization_name,
                    ),
                    "sort": corporation["corporation_name"],
                },
                "corporation_name": corporation["corporation_name"],
                "alliance_name": alliance_name,
                "mains_count": corporation["mains_count"],
                "characters_count": corporation["characters_count"],
                "unregistered_count": corporation["unregistered_count"],
                "compliance_percent": compliance_p,
                "is_compliant": is_compliant,
                "is_partly_compliant": compliance_p >= 85,
                "is_compliant_str": yesno_str(is_compliant),
            }
        )
    return JsonResponse({"data": data})


@login_required
@permission_required("memberaudit.reports_access")
def skill_sets_report_data(request) -> JsonResponse:
    """Render data view for skill sets report."""

    data = []
    for obj in _skillset_report_query():
        data.append(_build_skill_set_report_row(obj))

    return JsonResponse({"data": data})


def _build_skill_set_report_row(character: Character) -> dict:
    if character.main_character:
        main_name = character.main_character.character_name
        main_html = bootstrap_icon_plus_name_html(
            character.main_character.portrait_url(), main_name, avatar=True
        )
        main_corporation = character.main_character.corporation_name
        main_alliance = (
            character.main_character.alliance_name
            if character.main_character.alliance_name
            else ""
        )
        organization_html = format_html(
            "{}{}",
            main_corporation,
            f" [{character.main_character.alliance_ticker}]"
            if character.main_character.alliance_name
            else "",
        )
    else:
        main_html = main_name = ""
        main_corporation = main_alliance = organization_html = ""

    base_url = reverse("memberaudit:character_viewer", args=[character.pk])
    character_viewer_url = f"{base_url}?tab=skill_sets"
    character_html = bootstrap_icon_plus_name_html(
        character.eve_character.portrait_url(),
        character.eve_character.character_name,
        avatar=True,
        url=character_viewer_url,
    )

    passed_skill_sets = [
        bootstrap_icon_plus_name_html(
            skill_set_check.skill_set.ship_type.icon_url(
                DEFAULT_ICON_SIZE, variant=EveType.IconVariant.REGULAR
            )
            if skill_set_check.skill_set.ship_type
            else eveimageserver.type_icon_url(
                SKILL_SET_DEFAULT_ICON_TYPE_ID, size=DEFAULT_ICON_SIZE
            ),
            skill_set_check.skill_set.name,
        )
        for skill_set_check in character.passed_checks
    ]
    has_required_html = (
        "<br>".join(passed_skill_sets)
        if passed_skill_sets
        else '<i class="fas fa-times boolean-icon-false"></i>'
    )
    group_pk = character.group_pk if character.group_pk else 0
    state_name = character.user.profile.state.name if character.user else ""
    group_name = character.group_name
    is_doctrine = character.group_is_doctrine if character.group_is_doctrine else False
    if is_doctrine:
        group_name = f"Doctrine: {group_name}"
    return {
        "id": f"{group_pk}_{character.pk}",
        "group": group_name,
        "main": main_name,
        "main_html": main_html,
        "state": state_name,
        "organization_html": organization_html,
        "corporation": main_corporation,
        "alliance": main_alliance,
        "character": character.eve_character.character_name,
        "character_html": character_html,
        "has_required": has_required_html,
        "has_required_str": yesno_str(bool(passed_skill_sets)),
        "is_doctrine_str": yesno_str(is_doctrine),
        "is_main_str": yesno_str(character.is_main),
    }


def _skillset_report_query():
    group_ids = list(SkillSetGroup.objects.values_list("id", flat=True))
    passed_checks_qs = (
        CharacterSkillSetCheck.objects.filter(failed_required_skills__isnull=True)
        .select_related("skill_set", "skill_set__ship_type")
        .order_by("skill_set__name")
    )
    passed_skills_qs = CharacterSkillSetCheck.objects.filter(
        character=OuterRef("pk"), failed_required_skills__isnull=True
    )
    queryset = (
        Character.objects.select_related(
            "eve_character__character_ownership__user",
            "eve_character__character_ownership__user__profile__main_character",
            "eve_character__character_ownership__user__profile__state",
        )
        .exclude(
            eve_character__character_ownership__user__profile__state__pk=(
                get_guest_state_pk()
            )
        )
        .prefetch_related(
            Prefetch(
                "skill_set_checks", queryset=passed_checks_qs, to_attr="passed_checks"
            )
        )
        .filter(skill_set_checks__skill_set__groups__in=group_ids)
        .annotate(group_pk=F("skill_set_checks__skill_set__groups__pk"))
        .annotate(group_name=F("skill_set_checks__skill_set__groups__name"))
        .annotate(
            group_is_doctrine=F("skill_set_checks__skill_set__groups__is_doctrine")
        )
        .annotate(has_skills=Exists(passed_skills_qs))
        .distinct()
    )

    return queryset


class SkillSetReportDataTableView(DataTableView):
    """ "A data table view for skill set reports."""

    columns = ["group_name", "main", "state", "organization", "character", "skills"]
    group_column = "group_name"
    filters = [
        "group_name",
        ("eve_character__character_ownership__user__profile__state__name", _("State")),
        ("eve_character__alliance_name", _("Alliance")),
        ("eve_character__corporation_name", _("Corporation")),
        ("group_is_doctrine", _("Is Doctrine?")),
        "has_skills",
    ]
    search_fields = ["eve_character__character_name"]

    def get_initial_queryset(self):
        """Return base queryset."""
        return _skillset_report_query()

    def render_column(self, obj: Character, column: str) -> Any:
        """Return a rendered column."""
        has_main = bool(obj.main_character)

        if column == "main":
            if not has_main:
                return ""

            main_character_html = bootstrap_icon_plus_name_html(
                obj.main_character.portrait_url(),
                obj.main_character.character_name,
                avatar=True,
            )
            return main_character_html

        if column == "state":
            if not has_main:
                return ""
            return obj.user.profile.state.name

        if column == "organization":
            if not has_main:
                return ""

            organization_html = format_html(
                "{}{}",
                obj.main_character.corporation_name,
                f" [{obj.main_character.alliance_ticker}]"
                if obj.main_character.alliance_name
                else "",
            )
            return organization_html

        if column == "character":
            base_url = reverse("memberaudit:character_viewer", args=[obj.pk])
            character_viewer_url = f"{base_url}?tab=skill_sets"
            character_html = bootstrap_icon_plus_name_html(
                obj.eve_character.portrait_url(),
                obj.eve_character.character_name,
                avatar=True,
                url=character_viewer_url,
            )
            return character_html

        if column == "skills":
            passed_skill_sets = [
                bootstrap_icon_plus_name_html(
                    skill_set_check.skill_set.ship_type.icon_url(
                        DEFAULT_ICON_SIZE, variant=EveType.IconVariant.REGULAR
                    )
                    if skill_set_check.skill_set.ship_type
                    else eveimageserver.type_icon_url(
                        SKILL_SET_DEFAULT_ICON_TYPE_ID, size=DEFAULT_ICON_SIZE
                    ),
                    skill_set_check.skill_set.name,
                )
                for skill_set_check in obj.passed_checks
            ]
            has_required_html = format_html(
                "<br>".join(passed_skill_sets)
                if passed_skill_sets
                else '<i class="fas fa-times boolean-icon-false"></i>'
            )
            return has_required_html

        return super().render_column(obj, column)
