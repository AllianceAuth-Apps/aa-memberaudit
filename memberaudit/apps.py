"""Django app definition."""

from django.apps import AppConfig

from . import __version__


class MemberAuditConfig(AppConfig):
    name = "memberaudit"
    label = "memberaudit"
    verbose_name = f"Member Audit v{__version__}"

    def ready(self) -> None:
        from . import signals  # noqa: F401 pylint: disable=unused-import
