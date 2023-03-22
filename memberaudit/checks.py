from django.core.checks import Critical, Tags, register


@register(Tags.database)
def upgrade_from_1_x_check(app_configs, **kwargs):
    """Ensure users are upgrading to 2.0 first, when coming from 1.x"""
    from packaging.version import Version

    errors = []
    if version_text := _fetch_memberaudit_version():
        version = Version(version_text)
        if version.major < 2:
            errors.append(
                Critical(
                    "Can not upgrade directly from 1.x to 2.x",
                    hint=(
                        "You are upgrading from a 1.x version. "
                        "Please install and upgrade to 2.0 first "
                        "and follow the special upgrade instructions in the change notes. "
                        "Then you can upgrade to the newest version. "
                        "You can install the 2.0 version with the following command: "
                        "pip install aa-memberaudit==2.0.0"
                    ),
                    id="memberaudit.C001",
                )
            )
    return errors


def _fetch_memberaudit_version() -> str:
    """Fetch current version string of memberaudit."""
    try:
        from memberaudit import __version__
    except ImportError:
        return ""
    return __version__
