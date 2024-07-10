"""Manager for Character model."""

# pylint: disable=missing-class-docstring

from typing import Set

from django.contrib.auth.models import Permission, User
from django.db import models
from django.db.models import Case, Count, Q, Value, When

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.services.hooks import get_extension_logger
from app_utils.caching import ObjectCacheMixin
from app_utils.django import users_with_permission
from app_utils.logging import LoggerAddTag

from memberaudit import __title__

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class CharacterQuerySet(models.QuerySet):
    def eve_character_ids(self) -> Set[int]:
        """Return EveCharacter IDs of all characters in this QuerySet."""
        return set(self.values_list("eve_character__character_id", flat=True))

    def owned_by_user(self, user: User) -> models.QuerySet:
        """Filter character owned by user."""
        return self.filter(eve_character__character_ownership__user__pk=user.pk)

    def annotate_total_update_status(self) -> models.QuerySet:
        """Add total_update_status annotations."""
        from memberaudit.models import Character

        enabled_sections = list(Character.UpdateSection.enabled_sections())
        num_sections_total = len(enabled_sections)
        qs = (
            self.annotate(
                num_sections_total=Count(
                    "update_status_set",
                    filter=Q(update_status_set__section__in=enabled_sections),
                )
            )
            .annotate(
                num_sections_ok=Count(
                    "update_status_set",
                    filter=Q(
                        update_status_set__section__in=enabled_sections,
                        update_status_set__is_success=True,
                    ),
                )
            )
            .annotate(
                num_sections_failed=Count(
                    "update_status_set",
                    filter=Q(
                        update_status_set__section__in=enabled_sections,
                        update_status_set__is_success=False,
                    ),
                )
            )
            .annotate(
                num_sections_token_error=Count(
                    "update_status_set",
                    filter=Q(
                        update_status_set__section__in=enabled_sections,
                        update_status_set__has_token_error=True,
                    ),
                )
            )
            .annotate(
                total_update_status=Case(
                    When(
                        is_disabled=True,
                        then=Value(Character.TotalUpdateStatus.DISABLED.value),
                    ),
                    When(
                        num_sections_token_error=1,
                        then=Value(Character.TotalUpdateStatus.LIMITED_TOKEN.value),
                    ),
                    When(
                        num_sections_failed__gt=0,
                        then=Value(Character.TotalUpdateStatus.ERROR.value),
                    ),
                    When(
                        num_sections_ok=num_sections_total,
                        then=Value(Character.TotalUpdateStatus.OK.value),
                    ),
                    When(
                        num_sections_total__lt=num_sections_total,
                        then=Value(Character.TotalUpdateStatus.INCOMPLETE.value),
                    ),
                    default=Value(Character.TotalUpdateStatus.IN_PROGRESS.value),
                )
            )
        )
        return qs

    def disable_characters_with_no_owner(self) -> int:
        """Disable characters which have no owner. Return count of disabled characters."""
        orphaned_characters = self.filter(
            eve_character__character_ownership__isnull=True, is_disabled=False
        )
        if orphaned_characters.exists():
            orphans = list(
                orphaned_characters.values_list(
                    "eve_character__character_name", flat=True
                ).order_by("eve_character__character_name")
            )
            orphaned_characters.update(is_disabled=True)
            logger.info(
                "Disabled %d characters which do not belong to a user: %s",
                len(orphans),
                ", ".join(orphans),
            )
            return len(orphans)

        return 0


class CharacterManagerBase(ObjectCacheMixin, models.Manager):
    def characters_of_user_to_register_count(self, user: User) -> int:
        """Return count of a users's characters known to Auth,
        which needs to be (re-)registered.
        """
        unregistered = CharacterOwnership.objects.filter(
            user=user, character__memberaudit_character__isnull=True
        ).count()
        enabled_sections = list(self.model.UpdateSection.enabled_sections())
        token_errors = (
            self.filter(eve_character__character_ownership__user=user)
            .filter(
                Q(
                    update_status_set__section__in=enabled_sections,
                    update_status_set__has_token_error=True,
                )
                | Q(is_disabled=True),
            )
            .distinct()
            .count()
        )
        return unregistered + token_errors

    def user_has_scope(self, user: User) -> models.QuerySet:
        """Return characters the given user has the scope permission to access."""
        if user.has_perm("memberaudit.view_everything"):
            return self.all()
        qs = self.filter(eve_character__character_ownership__user=user)
        if (
            user.has_perm("memberaudit.view_same_alliance")
            and user.profile.main_character.alliance_id
        ):
            qs |= self.filter(
                eve_character__character_ownership__user__profile__main_character__alliance_id=(
                    user.profile.main_character.alliance_id
                )
            )
        elif user.has_perm("memberaudit.view_same_corporation"):
            qs |= self.filter(
                eve_character__character_ownership__user__profile__main_character__corporation_id=(
                    user.profile.main_character.corporation_id
                )
            )
        return qs

    def user_has_access(self, user: User) -> models.QuerySet:
        """Return characters the given user has permission to access
        via character viewer.
        """
        if user.has_perm("memberaudit.view_everything") and user.has_perm(
            "memberaudit.characters_access"
        ):
            return self.all()
        qs = self.filter(eve_character__character_ownership__user=user)
        if (
            user.has_perm("memberaudit.characters_access")
            and user.has_perm("memberaudit.view_same_alliance")
            and user.profile.main_character.alliance_id
        ):
            qs |= self.filter(
                eve_character__character_ownership__user__profile__main_character__alliance_id=(
                    user.profile.main_character.alliance_id
                )
            )
        elif user.has_perm("memberaudit.characters_access") and user.has_perm(
            "memberaudit.view_same_corporation"
        ):
            qs |= self.filter(
                eve_character__character_ownership__user__profile__main_character__corporation_id=(
                    user.profile.main_character.corporation_id
                )
            )
        if user.has_perm("memberaudit.view_shared_characters"):
            permission_to_share_characters = Permission.objects.select_related(
                "content_type"
            ).get(
                content_type__app_label=self.model._meta.app_label,
                codename="share_characters",
            )
            viewable_users = users_with_permission(permission_to_share_characters)
            qs |= self.filter(
                is_shared=True,
                eve_character__character_ownership__user__in=viewable_users,
            )
        return qs


CharacterManager = CharacterManagerBase.from_queryset(CharacterQuerySet)


class CharacterUpdateStatusQuerySet(models.QuerySet):
    def filter_enabled_sections(self) -> models.QuerySet:
        """Filter enabled sections."""
        from memberaudit.models import Character

        enabled_sections = list(Character.UpdateSection.enabled_sections())
        return self.filter(section__in=enabled_sections)


class CharacterUpdateStatusManagerBase(models.Manager):
    pass


CharacterUpdateStatusManager = CharacterUpdateStatusManagerBase.from_queryset(
    CharacterUpdateStatusQuerySet
)
