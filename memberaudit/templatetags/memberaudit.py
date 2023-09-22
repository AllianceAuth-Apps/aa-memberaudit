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
def tab_status_indicator(context, section: str) -> dict:
    sections_update_status = context["sections_update_status"]
    update_section = sections_update_status[str(section)]
    return {"has_error": not update_section.is_success}
