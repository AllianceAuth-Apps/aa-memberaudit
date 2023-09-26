"""Shared view components."""

from django.utils.html import format_html
from django.utils.translation import gettext_lazy
from eveuniverse.core import dotlan
from eveuniverse.models import EveSolarSystem

from app_utils.views import link_html

from memberaudit.app_settings import MEMBERAUDIT_APP_NAME
from memberaudit.constants import MY_DATETIME_FORMAT
from memberaudit.models import Character

UNGROUPED_SKILL_SET = gettext_lazy("[Ungrouped]")


def add_common_context(request, context: dict) -> dict:
    """Add the common context used by all view."""
    unregistered_count = Character.objects.characters_of_user_to_register_count(
        request.user
    )
    new_context = {
        **{
            "app_title": MEMBERAUDIT_APP_NAME,
            "unregistered_count": unregistered_count,
            "MY_DATETIME_FORMAT": MY_DATETIME_FORMAT,
        },
        **context,
    }
    return new_context


def eve_solar_system_to_html(solar_system: EveSolarSystem, show_region=True) -> str:
    """Convert solar system to HTML."""
    if solar_system.is_high_sec:
        css_class = "text-high-sec"
    elif solar_system.is_low_sec:
        css_class = "text-low-sec"
    else:
        css_class = "text-null-sec"

    region_html = (
        f" / {solar_system.eve_constellation.eve_region.name}" if show_region else ""
    )
    return format_html(
        '{} <span class="{}">{}</span>{}',
        link_html(dotlan.solar_system_url(solar_system.name), solar_system.name),
        css_class,
        round(solar_system.security_status, 1),
        region_html,
    )
