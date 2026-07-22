"""Django app definition."""

from django.apps import AppConfig

from memberaudit import __version__


class MemberAuditConfig(AppConfig):
    name = "memberaudit"
    label = "memberaudit"
    verbose_name = f"Member Audit v{__version__}"

    def ready(self) -> None:
        from memberaudit import checks  # noqa: F401 pylint: disable=unused-import
        from memberaudit import signals  # noqa: F401 pylint: disable=unused-import
