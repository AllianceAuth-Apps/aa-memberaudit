"""Template tags for Member Audit."""

from django import template
from django.urls import reverse

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
    """
    sections_update_status = context["sections_update_status"]

    is_success = True
    for section in sections:
        update_section = sections_update_status[str(section)]
        is_success &= update_section.is_success

    return {"has_error": not is_success}
