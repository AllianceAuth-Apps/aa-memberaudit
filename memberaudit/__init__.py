"""An Alliance Auth app that provides full access to Eve characters
and related reports for auditing, vetting and monitoring.
"""

# pylint: disable=invalid-name
default_app_config = "memberaudit.apps.MemberAuditConfig"

__version__ = "3.5.0a7"
__title__ = "Member Audit"

# TODO: Double-check recording of new updated-dates work for all sections
# TODO: Mover UpdateSectionResult to helper module
