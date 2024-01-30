"""Launcher views."""

import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import Permission
from django.db import transaction
from django.db.models import Sum
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from esi.decorators import token_required

from allianceauth.eveonline.models import EveCharacter
from allianceauth.notifications import notify
from allianceauth.services.hooks import get_extension_logger
from app_utils.django import users_with_permission
from app_utils.logging import LoggerAddTag

from memberaudit import __title__, tasks
from memberaudit.app_settings import MEMBERAUDIT_TASKS_NORMAL_PRIORITY
from memberaudit.core import eve_status
from memberaudit.models import (
    Character,
    CharacterMiningLedgerEntry,
    CharacterSkillpoints,
    CharacterWalletBalance,
    CharacterWalletJournalEntry,
    ComplianceGroupDesignation,
)

from ._common import add_common_context

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


@login_required
@permission_required("memberaudit.basic_access")
def index(request):
    """Render index view."""
    return redirect("memberaudit:launcher")


@login_required
@permission_required("memberaudit.basic_access")
def launcher(request) -> HttpResponse:
    """Render launcher view."""
    context_1 = _dashboard_panel(request)
    context_2 = _characters_panel(request)
    context = add_common_context(request, {**context_1, **context_2})
    return render(request, "memberaudit/launcher.html", context)


def _dashboard_panel(request: HttpRequest) -> dict:
    """Render context for dashboard panel."""
    characters = list(Character.objects.owned_by_user(request.user))
    total_wallet_isk = CharacterWalletBalance.objects.filter(
        character__in=characters
    ).aggregate(Sum("total"))["total__sum"]

    mining_entries = CharacterMiningLedgerEntry.objects.filter(character__in=characters)
    today = dt.date.today()
    total_mined_isk = (
        mining_entries.filter(date__year=today.year, date__month=today.month)
        .annotate_pricing()
        .aggregate(Sum("total"))["total__sum"]
    ) or 0

    wallet_entries = CharacterWalletJournalEntry.objects.filter(
        character__in=characters
    )
    today = dt.date.today()
    total_ratted_isk = (
        wallet_entries.filter(
            ref_type="bounty_prizes",
            date__year=today.year,
            date__month=today.month,
        ).aggregate(Sum("amount"))["amount__sum"]
        or 0
    )

    total_character_skillpoints = CharacterSkillpoints.objects.filter(
        character__in=characters
    ).aggregate(Sum("total"))["total__sum"]

    known_characters_count = EveCharacter.objects.filter(
        character_ownership__user=request.user
    ).count()
    registered_count = len(characters)
    try:
        registered_percent = round(registered_count / known_characters_count * 100)
    except ZeroDivisionError:
        registered_percent = None

    context = {
        "registered_count": registered_count,
        "known_characters_count": known_characters_count,
        "registered_percent": registered_percent,
        "total_wallet_isk": total_wallet_isk,
        "total_mined_isk": total_mined_isk,
        "total_ratted_isk": total_ratted_isk,
        "total_character_skillpoints": total_character_skillpoints,
    }
    return context


def _characters_panel(request: HttpRequest) -> dict:
    """Render context for character panel."""
    owned_chars_query = (
        EveCharacter.objects.filter(character_ownership__user=request.user)
        .select_related(
            "memberaudit_character",
            "memberaudit_character__location",
            "memberaudit_character__location__eve_solar_system",
            "memberaudit_character__location__location__eve_solar_system",
            "memberaudit_character__location__location__eve_solar_system__eve_constellation__eve_region",
            "memberaudit_character__skillpoints",
            "memberaudit_character__unread_mail_count",
            "memberaudit_character__wallet_balance",
        )
        .order_by("character_name")
    )
    has_auth_characters = owned_chars_query.exists()
    auth_characters = []
    unregistered_chars = []
    for eve_character in owned_chars_query:
        try:
            character: Character = eve_character.memberaudit_character
        except AttributeError:
            unregistered_chars.append(eve_character.character_name)
        else:
            auth_characters.append(
                {
                    "character_id": eve_character.character_id,
                    "character_name": eve_character.character_name,
                    "character": character,
                    "total_update_status": character.calc_total_update_status(),
                    "needs_refresh": character.is_disabled
                    or character.has_token_issue(),
                    "alliance_id": eve_character.alliance_id,
                    "alliance_name": eve_character.alliance_name,
                    "corporation_id": eve_character.corporation_id,
                    "corporation_name": eve_character.corporation_name,
                }
            )

    unregistered_chars = sorted(unregistered_chars)
    characters_need_token_refresh = sorted(
        obj["character_name"] for obj in auth_characters if obj["needs_refresh"]
    )

    try:
        main_character_id = request.user.profile.main_character.character_id
    except AttributeError:
        main_character_id = None

    context = {
        "page_title": _("My Characters"),
        "auth_characters": auth_characters,
        "has_auth_characters": has_auth_characters,
        "unregistered_chars": unregistered_chars,
        "has_registered_characters": len(auth_characters) > 0,
        "main_character_id": main_character_id,
        "characters_need_token_refresh": characters_need_token_refresh,
    }

    return context


@login_required
@permission_required("memberaudit.basic_access")
@token_required(scopes=Character.get_esi_scopes())
def add_character(request, token) -> HttpResponse:
    """Render add character view."""
    eve_character = get_object_or_404(EveCharacter, character_id=token.character_id)
    with transaction.atomic():
        character = Character.objects.update_or_create(
            eve_character=eve_character, defaults={"is_disabled": False}
        )[0]
    tasks.update_character.apply_async(
        kwargs={
            "character_pk": character.pk,
            "force_update": True,
            "ignore_stale": True,
        },
        priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY,
    )
    messages.success(
        request,
        format_html(
            "<strong>{}</strong> {}",
            eve_character,
            _(
                "has been registered. "
                "Note that it can take a minute until all character data is visible."
            ),
        ),
    )
    if ComplianceGroupDesignation.objects.exists():
        tasks.update_compliance_groups_for_user.apply_async(
            args=[request.user.pk], priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY
        )
    return redirect("memberaudit:launcher")


@login_required
@permission_required("memberaudit.basic_access")
def remove_character(request, character_pk: int) -> HttpResponse:
    """Render remove character view."""
    try:
        character = Character.objects.select_related(
            "eve_character__character_ownership__user", "eve_character"
        ).get(pk=character_pk)
    except Character.DoesNotExist:
        return HttpResponseNotFound(f"Character with pk {character_pk} not found")
    if character.user and character.user == request.user:
        character_name = character.eve_character.character_name

        # Notify that character has been dropped
        permission_to_notify = Permission.objects.select_related("content_type").get(
            content_type__app_label=Character._meta.app_label,
            codename="notified_on_character_removal",
        )
        title = _("%s: Character has been removed!") % __title__
        message = _("%(user)s has removed character %(character)s") % {
            "user": request.user,
            "character": character_name,
        }
        for to_notify in users_with_permission(permission_to_notify):
            if character.user_has_scope(to_notify):
                notify(user=to_notify, title=title, message=message, level="INFO")

        character.delete()
        messages.success(
            request, _("Removed character %s as requested.") % character_name
        )
        if ComplianceGroupDesignation.objects.exists():
            tasks.update_compliance_groups_for_user.apply_async(
                args=[request.user.pk], priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY
            )
    else:
        return HttpResponseForbidden(
            f"No permission to remove Character with pk {character_pk}"
        )
    return redirect("memberaudit:launcher")


@login_required
@permission_required(["memberaudit.basic_access", "memberaudit.share_characters"])
def share_character(request, character_pk: int) -> HttpResponse:
    """Render share character view."""
    try:
        character = Character.objects.select_related(
            "eve_character__character_ownership__user", "eve_character"
        ).get(pk=character_pk)
    except Character.DoesNotExist:
        return HttpResponseNotFound(f"Character with pk {character_pk} not found")
    if character.user and character.user == request.user:
        character.is_shared = True
        character.save()
    else:
        return HttpResponseForbidden(
            f"No permission to remove Character with pk {character_pk}"
        )
    return redirect("memberaudit:launcher")


@login_required
@permission_required("memberaudit.basic_access")
def unshare_character(request, character_pk: int) -> HttpResponse:
    """Render unshare character view."""
    try:
        character = Character.objects.select_related(
            "eve_character__character_ownership__user", "eve_character"
        ).get(pk=character_pk)
    except Character.DoesNotExist:
        return HttpResponseNotFound(f"Character with pk {character_pk} not found")
    if character.user and character.user == request.user:
        character.is_shared = False
        character.save()
    else:
        return HttpResponseForbidden(
            f"No permission to remove Character with pk {character_pk}"
        )
    return redirect("memberaudit:launcher")


@login_required
@permission_required("memberaudit.basic_access")
def player_count_data(request: HttpRequest) -> JsonResponse:
    """Return current Eve player count."""
    player_count = eve_status.player_count()
    data = {"player_count": player_count}
    return JsonResponse(data)
