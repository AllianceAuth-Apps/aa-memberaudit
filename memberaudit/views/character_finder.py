"""Character finder views."""

from dj_datatables_view.base_datatable_view import BaseDatatableView

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Case, F, Q, Value, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag
from app_utils.views import (
    bootstrap_icon_plus_name_html,
    fontawesome_link_button_html,
    yesno_str,
)

from memberaudit import __title__
from memberaudit.models import General

from ._common import add_common_context

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


@login_required
@permission_required("memberaudit.finder_access")
def character_finder(request) -> HttpResponse:
    """Render view for character finder."""
    context = {"page_title": _("Character Finder")}
    return render(
        request,
        "memberaudit/character_finder.html",
        add_common_context(request, context),
    )


# pylint: disable=too-many-ancestors
class CharacterFinderListJson(
    PermissionRequiredMixin, LoginRequiredMixin, BaseDatatableView
):
    """Server based datatable view for character finder."""

    model = EveCharacter
    permission_required = "memberaudit.finder_access"
    columns = [
        "character",
        "character_organization",
        "main_character",
        "main_organization",
        "state_name",
        "actions",
        "alliance_name",
        "corporation_name",
        "main_alliance_name",
        "main_corporation_name",
        "main_str",
        "unregistered_str",
        "character_id",
    ]

    # define column names that will be used in sorting
    # order is important and should be same as order of columns
    # displayed by datatables. For non sortable columns use empty
    # value like ''
    order_columns = [
        "character_name",
        "corporation_name",
        "character_ownership__user__profile__main_character__character_name",
        "character_ownership__user__profile__main_character__corporation_name",
        "character_ownership__user__profile__state__state_name",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]

    def get_initial_queryset(self):
        """Return initial queryset for this view."""
        return self.initial_queryset(self.request)

    @classmethod
    def initial_queryset(cls, request):
        """Return initial queryset for this view."""
        accessible_users = list(General.accessible_users(user=request.user))
        my_filter = Q(character_ownership__user__in=accessible_users)
        if request.user.has_perm("memberaudit.view_everything"):
            my_filter |= Q(memberaudit_character__isnull=False)
        elif request.user.has_perm("memberaudit.view_shared_characters"):
            my_filter |= Q(memberaudit_character__is_shared=True)
        eve_characters = EveCharacter.objects.select_related(
            "memberaudit_character",
            "character_ownership__user",
            "character_ownership__user__profile__main_character",
            "character_ownership__user__profile__state",
        ).filter(my_filter)
        return (
            eve_characters.annotate(
                unregistered_str=Case(
                    When(memberaudit_character=None, then=Value("yes")),
                    default=Value("no"),
                )
            )
            .annotate(
                is_orphan=Case(
                    When(character_ownership__isnull=True, then=Value(1)),
                    default=Value(0),
                )
            )
            .annotate(state_name=F("character_ownership__user__profile__state__name"))
        )

    def filter_queryset(self, qs):
        """use parameters passed in GET request to filter queryset"""

        qs = self._apply_search_filter(
            qs, 4, "character_ownership__user__profile__state__name"
        )
        qs = self._apply_search_filter(qs, 6, "alliance_name")
        qs = self._apply_search_filter(qs, 7, "corporation_name")
        qs = self._apply_search_filter(
            qs, 8, "character_ownership__user__profile__main_character__alliance_name"
        )
        qs = self._apply_search_filter(
            qs,
            9,
            "character_ownership__user__profile__main_character__corporation_name",
        )
        qs = self._apply_search_filter(
            qs, 10, "character_ownership__user__profile__main_character__character_name"
        )
        qs = self._apply_search_filter(qs, 11, "unregistered_str")

        search = self.request.GET.get("search[value]", None)
        if search:
            qs = qs.filter(
                Q(character_name__icontains=search)
                | Q(
                    character_ownership__user__profile__main_character__character_name__icontains=search
                )
            )
        return qs

    def _apply_search_filter(self, qs, column_num, field):
        my_filter = self.request.GET.get(f"columns[{column_num}][search][value]", None)
        if my_filter:
            if self.request.GET.get(f"columns[{column_num}][search][regex]", False):
                kwargs = {f"{field}__iregex": my_filter}
            else:
                kwargs = {f"{field}__istartswith": my_filter}
            return qs.filter(**kwargs)
        return qs

    def render_column(self, row, column):
        result = self._render_column_auth_character(row, column)
        if result:
            return result
        result = self._render_column_main_character(row, column)
        if result:
            return result
        result = self._render_column_memberaudit_character(row, column)
        if result:
            return result
        return super().render_column(row, column)

    def _render_column_auth_character(self, row, column):
        if column == "character_id":
            return row.character_id
        alliance_name = row.alliance_name if row.alliance_name else ""
        if column == "character_organization":
            return format_html(
                "{}<br><em>{}</em>",
                row.corporation_name,
                alliance_name,
            )
        if column == "alliance_name":
            return alliance_name
        if column == "corporation_name":
            return row.corporation_name
        return None

    def _render_column_main_character(self, row, column):
        try:
            main_character = row.character_ownership.user.profile.main_character
        except ObjectDoesNotExist:
            main_character = None
        is_main = main_character == row
        main_alliance_name = (
            main_character.alliance_name
            if main_character and main_character.alliance_name
            else ""
        )
        if column == "main_character":
            if main_character:
                return bootstrap_icon_plus_name_html(
                    main_character.portrait_url(),
                    main_character.character_name,
                    avatar=True,
                )
            return ""
        if column == "main_organization":
            if main_character:
                return format_html(
                    "{}<br><em>{}</em>",
                    main_character.corporation_name,
                    main_alliance_name,
                )
            return ""
        if column == "main_alliance_name":
            return main_alliance_name if main_character else ""
        if column == "main_corporation_name":
            return main_character.corporation_name if main_character else ""
        if column == "main_str":
            if main_character:
                return yesno_str(is_main)
            return ""
        return None

    def _render_column_memberaudit_character(self, row, column):
        try:
            character = row.memberaudit_character
        except ObjectDoesNotExist:
            character = None
            character_viewer_url = ""
        else:
            character_viewer_url = reverse(
                "memberaudit:character_viewer", args=[character.pk]
            )
        if column == "character":
            try:
                is_main = row.character_ownership.user.profile.main_character == row
            except ObjectDoesNotExist:
                is_main = False
            icons = []
            if is_main:
                icons.append(
                    mark_safe('<i class="fas fa-crown" title="Main character"></i>')
                )
            if character and character.is_shared:
                icons.append(
                    mark_safe('<i class="far fa-eye" title="Shared character"></i>')
                )
            if not character:
                icons.append(
                    mark_safe(
                        '<i class="fas fa-exclamation-triangle" title="Unregistered character"></i>'
                    )
                )
            character_text = format_html_join(
                mark_safe("&nbsp;"), "{}", ([html] for html in icons)
            )
            if row.is_orphan:
                character_text += mark_safe(" [orphan]")
            return bootstrap_icon_plus_name_html(
                row.portrait_url(),
                row.character_name,
                avatar=True,
                url=character_viewer_url,
                text=character_text,
            )
        if column == "actions":
            if character_viewer_url:
                actions_html = fontawesome_link_button_html(
                    url=character_viewer_url,
                    fa_code="fas fa-search",
                    button_type="primary",
                )
            else:
                actions_html = ""
            return actions_html
        return None


@login_required
@permission_required("memberaudit.finder_access")
def character_finder_list_fdd_data(request) -> JsonResponse:
    """Provide lists for drop down fields."""
    result = {}
    qs = CharacterFinderListJson.initial_queryset(request)
    columns = request.GET.get("columns")
    if columns:
        for column in columns.split(","):
            if column == "alliance_name":
                options = qs.exclude(alliance_id__isnull=True).values_list(
                    "alliance_name", flat=True
                )
            elif column == "corporation_name":
                options = qs.values_list("corporation_name", flat=True)
            elif column == "main_alliance_name":
                options = qs.exclude(
                    Q(character_ownership__user__profile__main_character__isnull=True)
                    | Q(
                        character_ownership__user__profile__main_character__alliance_id__isnull=True
                    )
                ).values_list(
                    "character_ownership__user__profile__main_character__alliance_name",
                    flat=True,
                )
            elif column == "main_corporation_name":
                options = qs.exclude(
                    character_ownership__user__profile__main_character__isnull=True
                ).values_list(
                    "character_ownership__user__profile__main_character__corporation_name",
                    flat=True,
                )
            elif column == "main_str":
                options = qs.exclude(
                    character_ownership__user__profile__main_character__isnull=True
                ).values_list(
                    "character_ownership__user__profile__main_character__character_name",
                    flat=True,
                )
            elif column == "unregistered_str":
                options = [
                    "yes" if elem is None else "no"
                    for elem in qs.values_list("memberaudit_character", flat=True)
                ]
            elif column == "state_name":
                options = [
                    "-" if elem is None else elem
                    for elem in qs.values_list(
                        "character_ownership__user__profile__state__name", flat=True
                    )
                ]
            else:
                options = [f"** ERROR: Invalid column name '{column}' **"]
            result[column] = sorted(list(set(options)), key=str.casefold)
    return JsonResponse(result, safe=False)
