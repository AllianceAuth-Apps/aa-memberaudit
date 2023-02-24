from typing import Optional

import unidecode

from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from . import __title__

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def get_or_create_esi_or_none(
    prop_name: str, dct: dict, Model: type
) -> Optional[models.Model]:
    """Gets or creates a new eveuniverse object from a dictionary entry.

    return the object on success or None
    """
    if dct.get(prop_name):
        obj, _ = Model.objects.get_or_create_esi(id=dct.get(prop_name))
    else:
        obj = None

    return obj


def get_or_create_or_none(
    prop_name: str, dct: dict, Model: type
) -> Optional[models.Model]:
    """Get or creates a Django object from a dictionary entry or returns None."""
    if dct.get(prop_name):
        obj, _ = Model.objects.get_or_create(id=dct.get(prop_name))
        return obj
    return None


def get_or_none(prop_name: str, dct: dict, Model: type) -> Optional[models.Model]:
    """Gets a new Django object from a dictionary entry
    or returns None if it does not exist."""
    id = dct.get(prop_name)
    if id:
        try:
            return Model.objects.get(id=id)
        except Model.DoesNotExist:
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
    """Get an unidecoded slug from a string

    :param app_name:
    :type app_name:
    :return:
    :rtype:
    """
    return slugify(unidecode.unidecode(app_name), allow_unicode=True)
