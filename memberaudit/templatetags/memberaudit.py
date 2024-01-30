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

    Expects these keys in the context: "sections_update_status", "total_update_status"
    """
    sections_update_status = context["sections_update_status"]
    result = {"tab_update_status": Character.TotalUpdateStatus.OK}

    if context["total_update_status"] is Character.TotalUpdateStatus.DISABLED:
        return result

    is_success = True
    is_complete = True
    for section in sections:
        section_obj = Character.UpdateSection(section)  # make sure section is valid
        try:
            update_section = sections_update_status[str(section_obj)]
        except KeyError:
            is_complete = False
        else:
            if update_section.is_success is not None:
                is_success &= update_section.is_success

    if not is_success:
        tab_update_status = Character.TotalUpdateStatus.ERROR
    elif not is_complete:
        tab_update_status = Character.TotalUpdateStatus.INCOMPLETE
    else:
        tab_update_status = Character.TotalUpdateStatus.OK
    result["tab_update_status"] = tab_update_status
    return result


@register.inclusion_tag("memberaudit/partials/natural_number.html", takes_context=False)
def natural_number(value) -> dict:
    """Render a number humanized and with the exact number as tooltip."""
    return {"value": value}
