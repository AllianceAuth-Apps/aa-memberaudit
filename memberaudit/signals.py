"""Signals for Member Audit."""

from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import pre_save
from django.dispatch import receiver

from allianceauth.groupmanagement.models import AuthGroup


@receiver(pre_save, sender=AuthGroup)
def ensure_compliance_groups_stay_internal(instance, **kwargs):
    """Prevent changing a compliance group to non-internal."""
    try:
        instance.group.compliancegroupdesignation
    except ObjectDoesNotExist:
        pass
    else:
        instance.internal = True
