from django.db.models import Sum
from django.http import HttpRequest
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from memberaudit.models import (
    Character,
    CharacterMiningLedgerEntry,
    CharacterSkillpoints,
    CharacterWalletBalance,
    CharacterWalletJournalEntry,
)
from memberaudit.providers import esi

from ._common import add_common_context


def my_dashboard(request: HttpRequest):
    result = esi.client.Status.get_status().results()
    characters = list(Character.objects.owned_by_user(request.user))
    total_character_isk = CharacterWalletBalance.objects.filter(
        character__in=characters
    ).aggregate(Sum("total"))["total__sum"]
    total_mined_isk = (
        CharacterMiningLedgerEntry.objects.filter(character__in=characters)
        .annotate_pricing()
        .aggregate(Sum("total"))["total__sum"]
    )
    total_ratted_isk = CharacterWalletJournalEntry.objects.filter(
        character__in=characters, ref_type="bounty_prizes"
    ).aggregate(Sum("amount"))["amount__sum"]
    total_character_skillpoints = CharacterSkillpoints.objects.filter(
        character__in=characters
    ).aggregate(Sum("total"))["total__sum"]
    context = {
        "page_title": _("My Dashboard"),
        "player_count": result["players"],
        "registered_count": len(characters),
        "total_character_isk": total_character_isk or 123456789,
        "total_mined_isk": total_mined_isk or 123456789,
        "total_ratted_isk": total_ratted_isk or 123456789,
        "total_character_skillpoints": total_character_skillpoints or 123456789,
    }
    return render(
        request, "memberaudit/dashboard.html", add_common_context(request, context)
    )
