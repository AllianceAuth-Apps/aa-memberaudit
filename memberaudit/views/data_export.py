"""Data export views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__, tasks
from memberaudit.app_settings import MEMBERAUDIT_DATA_EXPORT_MIN_UPDATE_AGE
from memberaudit.core import data_exporters
from memberaudit.models import Character

from ._common import add_common_context

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


@login_required
@permission_required("memberaudit.exports_access")
def data_export(request) -> HttpResponse:
    """Render data export view."""
    topics = data_exporters.topics_and_export_files()
    context = {
        "page_title": _("Data Export"),
        "topics": topics,
        "character_count": Character.objects.count(),
        "minutes_until_next_update": MEMBERAUDIT_DATA_EXPORT_MIN_UPDATE_AGE,
    }
    return render(
        request, "memberaudit/data_export.html", add_common_context(request, context)
    )


@login_required
@permission_required("memberaudit.exports_access")
def download_export_file(request, topic: str) -> FileResponse:
    """Render file view for downloading an export file."""
    exporter = data_exporters.DataExporter.create_exporter(topic)
    destination = data_exporters.default_destination()
    zip_file = destination / exporter.output_basename.with_suffix(".zip")
    if not zip_file.exists():
        raise Http404(f"Could not find export file for {topic}")
    logger.info("Returning file %s for download of topic %s", zip_file, topic)
    return FileResponse(zip_file.open("rb"))


@login_required
@permission_required("memberaudit.exports_access")
def data_export_run_update(request, topic: str):
    """Render view for running data export update."""
    tasks.export_data_for_topic.delay(topic=topic, user_pk=request.user.pk)
    messages.info(
        request,
        _(
            "Data export for topic %s has been started. "
            "This can take a couple of minutes. "
            "You will get a notification once it is completed.",
        )
        % topic,
    )
    return redirect("memberaudit:data_export")
