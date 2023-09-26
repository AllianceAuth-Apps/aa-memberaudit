"""Template tags for Member Audit."""

from django import template
from django.urls import reverse

from memberaudit.models import Character

register = template.Library()


@register.simple_tag
def navactive_2(request, url_name: str, *args):
    """Return the active class name for navs."""
    url = reverse(url_name, args=args)
    if request.path == url:
        return "active"
    return ""


@register.inclusion_tag(
    "memberaudit/partials/character_viewer/tab_status_indicator.html",
    takes_context=True,
)
def tab_status_indicator(context, *sections) -> dict:
    """Render status indicator for a character tab.

    Show as error when at least one section has an error.

    Expects these keys in the context: "sections_update_status", "update_status"
    """
    sections_update_status = context["sections_update_status"]
    update_status = context["update_status"]
    result = {"has_error": False}

    if update_status is Character.TotalUpdateStatus.DISABLED:
        return result

    is_success = True
    for section in sections:
        section_obj = Character.UpdateSection(section)  # make sure section is valid
        try:
            update_section = sections_update_status[str(section_obj)]
        except KeyError:
            continue
        is_success &= update_section.is_success

    result["has_error"] = not is_success
    return result
