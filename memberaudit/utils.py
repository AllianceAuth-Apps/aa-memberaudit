"""Generic helpers."""

from typing import Any, Optional

import unidecode

from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def get_or_create_esi_or_none(
    prop_name: str, dct: dict, model_class: type
) -> Optional[Any]:
    """Get or create a new eveuniverse object from a dictionary entry.

    Return the object on success or None.
    """
    if obj_id := dct.get(prop_name):
        obj = model_class.objects.get_or_create_esi(id=obj_id)[0]  # type: ignore
        return obj

    return None


def get_or_create_or_none(
    prop_name: str, dct: dict, model_class: type
) -> Optional[Any]:
    """Get or creates a Django object from a dictionary entry
    or returns None when the entry is none or does not exist.
    """
    if obj_id := dct.get(prop_name):
        obj = model_class.objects.get_or_create(id=obj_id)[0]  # type: ignore
        return obj

    return None


def get_or_none(prop_name: str, dct: dict, model_class: type) -> Optional[Any]:
    """Get a new Django object from a dictionary entry
    or return None if it does not exist.
    """
    if obj_id := dct.get(prop_name):
        try:
            return model_class.objects.get(id=obj_id)  # type: ignore
        except model_class.DoesNotExist:  # type: ignore
            pass

    return None


def filter_groups_available_to_user(
    groups_qs: models.QuerySet, user: User
) -> models.QuerySet:
    """Filter out groups not available to user, e.g. due to state restrictions."""
    return groups_qs.filter(authgroup__states=None) | groups_qs.filter(
        authgroup__states=user.profile.state
    )


def clear_users_from_group(group):
    """Remove all users from given group.

    Workaround for using the clear method,
    which can create problems due to Auth issue #1268
    """
    # TODO: Refactor once Auth issue is fixed
    for user in group.user_set.all():
        user.groups.remove(group)


def get_unidecoded_slug(app_name: str = "Member Audit") -> str:
    """Get an unidecoded slug from a string.

    :param app_name:
    :type app_name:
    :return:
    :rtype:
    """
    return slugify(unidecode.unidecode(app_name), allow_unicode=True)
