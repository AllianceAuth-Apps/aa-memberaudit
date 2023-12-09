"""Character views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import Permission
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as __
from esi.decorators import token_required

from allianceauth.eveonline.models import EveCharacter
from allianceauth.notifications import notify
from allianceauth.services.hooks import get_extension_logger
from app_utils.django import users_with_permission
from app_utils.logging import LoggerAddTag

from memberaudit import __title__, tasks
from memberaudit.app_settings import MEMBERAUDIT_TASKS_NORMAL_PRIORITY
from memberaudit.models import Character, ComplianceGroupDesignation

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
        "page_title": __("My Characters"),
        "auth_characters": auth_characters,
        "has_auth_characters": has_auth_characters,
        "unregistered_chars": unregistered_chars,
        "has_registered_characters": len(auth_characters) > 0,
        "main_character_id": main_character_id,
        "characters_need_token_refresh": characters_need_token_refresh,
    }

    return render(
        request, "memberaudit/launcher.html", add_common_context(request, context)
    )


@login_required
@permission_required("memberaudit.basic_access")
@token_required(scopes=Character.get_esi_scopes())
def add_character(request, token) -> HttpResponse:
    """Render add character view."""
    eve_character = get_object_or_404(EveCharacter, character_id=token.character_id)
    with transaction.atomic():
        character, _ = Character.objects.update_or_create(
            eve_character=eve_character, defaults={"is_disabled": False}
        )
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
            __(
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
        title = __("%s: Character has been removed!") % __title__
        message = __("%(user)s has removed character %(character)s") % {
            "user": request.user,
            "character": character_name,
        }
        for to_notify in users_with_permission(permission_to_notify):
            if character.user_has_scope(to_notify):
                notify(user=to_notify, title=title, message=message, level="INFO")

        character.delete()
        messages.success(
            request, __("Removed character %s as requested.") % character_name
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
