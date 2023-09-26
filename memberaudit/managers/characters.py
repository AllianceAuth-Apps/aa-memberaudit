"""Manager for Character model."""
# pylint: disable=missing-class-docstring

from copy import deepcopy
from math import floor
from typing import Set

from django.conf import settings as auth_settings
from django.contrib.auth.models import Permission, User
from django.db import models
from django.db.models import (
    Avg,
    Case,
    Count,
    ExpressionWrapper,
    F,
    Max,
    Min,
    Q,
    Value,
    When,
)

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.services.hooks import get_extension_logger
from app_utils.caching import ObjectCacheMixin
from app_utils.django import users_with_permission
from app_utils.logging import LoggerAddTag

from memberaudit import __title__, app_settings

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
    def statistics(self) -> dict:
        """Return detailed statistics about the last update run and the app."""

        from memberaudit.models import (
            Character,
            CharacterAsset,
            CharacterContact,
            CharacterContract,
            CharacterMail,
            SkillSet,
            SkillSetGroup,
        )

        all_characters_count = Character.objects.count()

        settings = self._fetch_settings()

        update_stats = self._calc_update_stats(all_characters_count, settings)

        return {
            "app_totals": {
                "users_count": User.objects.filter(
                    character_ownerships__character__memberaudit_character__isnull=False
                )
                .distinct()
                .count(),
                "all_characters_count": all_characters_count,
                "skill_set_groups_count": SkillSetGroup.objects.count(),
                "skill_sets_count": SkillSet.objects.count(),
                "assets_count": CharacterAsset.objects.count(),
                "mails_count": CharacterMail.objects.count(),
                "contacts_count": CharacterContact.objects.count(),
                "contracts_count": CharacterContract.objects.count(),
            },
            "settings": settings,
            "update_statistics": update_stats,
        }

    def _calc_update_stats(self, all_characters_count, settings):
        from memberaudit.models import Character

        update_stats = {}
        if self.count() > 0:
            qs_base, root_task_ids = self._calc_qs_base()
            # per ring
            for ring in range(1, 4):
                sections = Character.sections_in_ring(ring)

                # calc totals
                qs_ring = qs_base.filter(section__in=sections)
                self._calc_totals(
                    all_characters_count,
                    settings,
                    root_task_ids,
                    update_stats,
                    ring,
                    qs_ring,
                )

                # calc section stats
                for section in sections:
                    self._update_section(qs_base, section, update_stats, ring)

                self._update_character_ring_counts(
                    all_characters_count, update_stats, ring, sections, qs_ring
                )

        return update_stats

    def _update_character_ring_counts(
        self, all_characters_count, update_stats, ring, sections, qs
    ):
        from memberaudit.models import Character

        ring_characters_count = (
            Character.objects.filter(update_status_set__in=qs)
            .annotate(num_sections=Count("update_status_set__section"))
            .filter(num_sections=len(sections))
            .count()
        )
        update_stats[f"ring_{ring}"]["total"][
            "characters_count"
        ] = ring_characters_count
        update_stats[f"ring_{ring}"]["total"]["completed"] = (
            ring_characters_count == all_characters_count
        )

    def _calc_qs_base(self):
        from memberaudit.models import Character

        qs_base = self.filter(
            is_success=True,
            started_at__isnull=False,
            finished_at__isnull=False,
        ).exclude(root_task_id="", parent_task_id="")
        root_task_ids = {
            ring: self._root_task_id_or_none(
                qs_base.filter(section__in=Character.sections_in_ring(ring))
                .order_by("-finished_at")
                .first()
            )
            for ring in range(1, 4)
        }
        duration_expression = ExpressionWrapper(
            F("finished_at") - F("started_at"),
            output_field=models.fields.DurationField(),
        )
        qs_base = qs_base.filter(root_task_id__in=root_task_ids.values()).annotate(
            duration=duration_expression
        )
        return qs_base, root_task_ids

    def _calc_totals(
        self, all_characters_count, settings, root_task_ids, update_stats, ring, qs
    ):  # pylint: disable=too-many-locals
        try:
            first = qs.order_by("started_at").first()
            last = qs.order_by("finished_at").last()
            started_at = first.started_at
            finished_at = last.finished_at
            duration = round((finished_at - started_at).total_seconds(), 1)
        except (KeyError, AttributeError):
            first = None
            last = None
            duration = None
            started_at = None
            finished_at = None

        available_time = (
            settings[f"MEMBERAUDIT_UPDATE_STALE_RING_{ring}"]
            - settings["MEMBERAUDIT_UPDATE_STALE_OFFSET"]
        ) * 60
        throughput = floor(all_characters_count / duration * 3600) if duration else None
        within_boundaries = duration < available_time if duration else None
        update_stats[f"ring_{ring}"] = {
            "total": {
                "duration": duration,
                "started_at": started_at,
                "finished_at": finished_at,
                "root_task_id": root_task_ids.get(ring),
                "throughput_est": throughput,
                "available_time": available_time,
                "within_available_time": within_boundaries,
            },
            "max": {},
            "sections": {},
        }

        # add longest running section w/ character
        obj = qs.order_by("-duration").first()
        update_stats[f"ring_{ring}"]["max"] = self._info_from_obj(obj)

        # add first and last section
        update_stats[f"ring_{ring}"]["first"] = self._info_from_obj(first)
        update_stats[f"ring_{ring}"]["last"] = self._info_from_obj(last)

        return first, last

    def _update_section(self, qs_base, section, update_stats, ring):
        try:
            section_max = round(
                qs_base.filter(section=section)
                .aggregate(Max("duration"))["duration__max"]
                .total_seconds(),
                1,
            )
            section_avg = round(
                qs_base.filter(section=section)
                .aggregate(Avg("duration"))["duration__avg"]
                .total_seconds(),
                1,
            )
            section_min = round(
                qs_base.filter(section=section)
                .aggregate(Min("duration"))["duration__min"]
                .total_seconds(),
                1,
            )
        except (KeyError, AttributeError):
            section_max = (None,)
            section_avg = None
            section_min = None

        update_stats[f"ring_{ring}"]["sections"].update(
            {
                str(section): {
                    "max": section_max,
                    "avg": section_avg,
                    "min": section_min,
                }
            }
        )

    def _fetch_settings(self):
        settings = {
            name: value
            for name, value in vars(app_settings).items()
            if name.startswith("MEMBERAUDIT_")
        }
        schedule = deepcopy(auth_settings.CELERYBEAT_SCHEDULE)
        for name, details in schedule.items():
            for key, value in details.items():
                if key == "schedule":
                    schedule[name][key] = str(value)

        settings["CELERYBEAT_SCHEDULE"] = schedule
        return settings

    @staticmethod
    def _root_task_id_or_none(obj):
        try:
            return obj.root_task_id
        except AttributeError:
            return None

    @staticmethod
    def _info_from_obj(obj) -> dict:
        try:
            section_name = str(obj.section)
            character_name = str(obj.character)
            duration = round(obj.duration.total_seconds(), 1)
        except (KeyError, AttributeError):
            section_name = None
            character_name = None
            duration = None

        return {
            "section": section_name,
            "character": character_name,
            "duration": duration,
        }


CharacterUpdateStatusManager = CharacterUpdateStatusManagerBase.from_queryset(
    CharacterUpdateStatusQuerySet
)
