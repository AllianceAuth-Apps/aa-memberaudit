from typing import List, Optional

from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models import Max, Prefetch
from django.forms.models import BaseInlineFormSet
from django.shortcuts import redirect, render
from django.utils.html import format_html
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from eveuniverse.models import EveType

from allianceauth.authentication.models import State

from memberaudit import tasks
from memberaudit.app_settings import MEMBERAUDIT_TASKS_NORMAL_PRIORITY
from memberaudit.constants import EveCategoryId
from memberaudit.models import (
    Character,
    CharacterUpdateStatus,
    ComplianceGroupDesignation,
    EveShipType,
    EveSkillType,
    Location,
    SkillSet,
    SkillSetGroup,
    SkillSetSkill,
)


class ComplianceGroupDesignationForm(forms.ModelForm):
    class Meta:
        model = ComplianceGroupDesignation
        fields = ("group",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.fields["group"].queryset = Group.objects.filter(
                authgroup__internal=True, compliancegroupdesignation__isnull=True
            ).order_by("name")
        except KeyError:
            pass


@admin.register(ComplianceGroupDesignation)
class ComplianceGroupDesignationAdmin(admin.ModelAdmin):
    form = ComplianceGroupDesignationForm
    ordering = ("group__name",)
    list_display = ("_group_name", "_states")
    list_display_links = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("group").prefetch_related("group__authgroup__states")

    def save_model(self, request, obj, *args, **kwargs) -> None:
        super().save_model(request, obj, *args, **kwargs)
        tasks.add_compliant_users_to_group.apply_async(
            args=[obj.group.pk], priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY
        )  # type: ignore

    def delete_queryset(self, request, queryset) -> None:
        for obj in queryset:
            tasks.clear_users_from_group.apply_async(
                args=[obj.group.pk], priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY
            )  # type: ignore
            obj.delete()

    @admin.display(ordering="group__name")
    def _group_name(self, obj) -> str:
        return obj.group.name

    @admin.display(description=_("Restricted to states"))
    def _states(self, obj):
        states = [state.name for state in obj.group.authgroup.states.all()]
        return sorted(states) if states else "-"

    def has_change_permission(self, request, obj=None):
        return False


class EveUniverseEntityModelAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    ordering = ["name"]
    search_fields = ["name"]


@admin.register(EveShipType)
class EveShipTypeAdmin(EveUniverseEntityModelAdmin):
    pass


@admin.register(EveSkillType)
class EveSkillTypeAdmin(EveUniverseEntityModelAdmin):
    pass


class SyncStatusAdminInline(admin.TabularInline):
    model = CharacterUpdateStatus
    fields = (
        "section",
        "is_success",
        "last_error_message",
        "started_at",
        "finished_at",
        "root_task_id",
    )
    ordering = ["section"]

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CharacterUpdateStatusListFilter(admin.SimpleListFilter):
    """Custom filter for update status with counts."""

    title = _("update status")
    parameter_name = "update_status"

    def lookups(self, request, model_admin):
        qs = model_admin.get_queryset(request)
        counts = []
        for status in Character.UpdateStatus:
            counts.append((status, qs.filter(update_status=status.value).count()))
        result = tuple(
            [
                (status.value, status.label.title() + f" ({count:,})")
                for status, count in counts
            ]
        )
        return result

    def queryset(self, request, queryset):
        for value in Character.UpdateStatus.values:
            if self.value() == value:
                return queryset.filter(update_status=value)
        return queryset


class CharacterStateListFilter(admin.SimpleListFilter):
    """Custom state filter to include filtering of characters without main."""

    title = _("state")
    parameter_name = "state"
    _NO_MAIN_KEY = "_NO_MAIN"

    def __init__(self, *args, **kwargs) -> None:
        self._states = State.objects.order_by("-priority").values_list(
            "name", flat=True
        )
        super().__init__(*args, **kwargs)

    def lookups(self, request, model_admin):
        qs = model_admin.get_queryset(request)
        counts = []
        for name in self._states:
            counts.append(
                (
                    name,
                    qs.filter(
                        eve_character__character_ownership__user__profile__state__name=name
                    ).count(),
                )
            )
        result = [(name, name + f" ({count:,})") for name, count in counts]
        count_no_main = qs.filter(
            eve_character__character_ownership__isnull=True
        ).count()
        result.append((self._NO_MAIN_KEY, _("No main") + f" ({count_no_main:,})"))
        return result

    def queryset(self, request, queryset):
        value = self.value()
        if value == self._NO_MAIN_KEY:
            return queryset.filter(eve_character__character_ownership__isnull=True)
        for name in self._states:
            if value == name:
                return queryset.filter(
                    eve_character__character_ownership__user__profile__state__name=name
                )
        return queryset


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    class Media:
        css = {
            "all": ("authentication/css/admin.css", "memberaudit/css/admin.css"),
        }

    list_display = (
        "_character_pic",
        "_character",
        "_main",
        "_state",
        "_organization",
        "_created_at",
        "_enabled",
        "_last_update_at",
        "_update_status",
        "_missing_sections",
    )
    list_display_links = (
        "_character_pic",
        "_character",
    )
    list_filter = (
        CharacterUpdateStatusListFilter,
        "is_disabled",
        CharacterStateListFilter,
        "created_at",
        "eve_character__character_ownership__user__profile__main_character__alliance_name",
    )
    list_select_related = (
        "eve_character__character_ownership__user",
        "eve_character__character_ownership__user__profile__main_character",
        "eve_character__character_ownership__user__profile__state",
        "eve_character",
    )
    ordering = ["eve_character__character_name"]
    search_fields = [
        "eve_character__character_name",
        "eve_character__character_ownership__user__profile__main_character__character_name",
        "eve_character__character_ownership__user__profile__main_character__corporation_name",
        "eve_character__character_ownership__user__profile__main_character__alliance_name",
    ]
    exclude = ("mailing_lists",)

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        return (
            qs.prefetch_related("update_status_set")
            .annotate(last_update_at=Max("update_status_set__finished_at"))
            .annotate_update_status()
        )

    def get_actions(self, request):
        """Remove the default delete action from the drop-down."""
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    @admin.display(description="")
    def _character_pic(self, obj: Character):
        character = obj.eve_character
        return format_html(
            '<img src="{}" class="img-circle">', character.portrait_url(size=32)
        )

    @admin.display(ordering="eve_character__character_name", description=_("character"))
    def _character(self, obj: Character) -> str:
        return str(obj.eve_character)

    @admin.display(ordering="is_disabled", boolean=True, description=_("enabled"))
    def _enabled(self, obj: Character) -> bool:
        return not obj.is_disabled

    @admin.display(
        ordering="eve_character__character_ownership__user__profile__main_character",
        description=_("main"),
    )
    def _main(self, obj: Character) -> Optional[str]:
        try:
            name = obj.main_character.character_name
        except AttributeError:
            return None
        return str(name)

    @admin.display(
        ordering="eve_character__character_ownership__user__profile__state__name",
        description=_("state"),
    )
    def _state(self, obj: Character) -> Optional[str]:
        try:
            return str(obj.user.profile.state)
        except AttributeError:
            return None

    @admin.display(
        ordering="eve_character__character_ownership__user__profile__main_character__corporation_name",
        description=_("organization"),
    )
    def _organization(self, obj: Character) -> Optional[str]:
        if not obj.main_character:
            return None
        result = obj.main_character.corporation_name
        if result and obj.main_character.alliance_ticker:
            result += f" [{obj.main_character.alliance_ticker}]"
        return result

    @admin.display(ordering="update_status", description=_("update status"))
    def _update_status(self, obj: Character):
        css_class_map = {
            Character.UpdateStatus.INCOMPLETE: "text-warning",
            Character.UpdateStatus.ERROR: "text-danger",
            Character.UpdateStatus.DISABLED: "text-muted",
        }
        label = Character.UpdateStatus(obj.update_status).label.title()
        if css_class := css_class_map.get(obj.update_status):
            return format_html('<span class="{}">{}</span>', css_class, label)
        return label

    @admin.display(ordering="created_at", description=_("created"))
    def _created_at(self, obj: Character):
        return obj.created_at

    @admin.display(ordering="last_update_at", description=_("last update"))
    def _last_update_at(self, obj: Character):
        return obj.last_update_at

    def _missing_sections(self, obj):
        existing = {x.section for x in obj.update_status_set.all()}
        all_sections = set(Character.UpdateSection.values)
        missing = all_sections.difference(existing)
        if missing:
            return sorted(
                [Character.UpdateSection.display_name(obj) for obj in missing]
            )
        return None

    actions = [
        "delete_characters",
        "update_characters",
        "update_assets",
        "update_location",
        "update_online_status",
        "enable_characters",
        "disable_characters",
    ]

    @admin.display(description=_("Delete selected characters"))
    def delete_characters(self, request, queryset):
        if "apply" in request.POST:
            for obj in queryset:
                tasks.delete_character.apply_async(
                    kwargs={"character_pk": obj.pk},
                    priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY,
                )  # type: ignore
            self.message_user(
                request,
                _("Started deleting %d character(s). This can take a minute.")
                % queryset.count(),
            )
            return redirect(request.get_full_path())
        return render(
            request,
            "admin/memberaudit/character/confirm_character_deletion.html",
            {
                "title": _("Are you sure you want to delete these characters?"),
                "queryset": queryset.all(),
            },
        )

    @admin.display(description=_("Update selected characters from EVE server"))
    def update_characters(self, request, queryset):
        for obj in queryset:
            tasks.update_character.apply_async(
                kwargs={"character_pk": obj.pk, "force_update": True},
                priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY,
            )  # type: ignore
            self.message_user(request, _("Started updating character %s.") % obj)

    @admin.display(
        description=_("Update assets for selected characters from EVE server")
    )
    def update_assets(self, request, queryset):
        for obj in queryset:
            tasks.update_character_assets.apply_async(
                kwargs={"character_pk": obj.pk, "force_update": True},
                priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY,
            )  # type: ignore
            self.message_user(
                request, _("Started updating assets for character %s.") % obj
            )

    @admin.display(
        description=(
            _(
                "Update %s for selected characters from EVE server"
                % {
                    Character.UpdateSection.display_name(
                        Character.UpdateSection.LOCATION
                    )
                }
            )
        )
    )
    def update_location(self, request, queryset):
        section = Character.UpdateSection.LOCATION
        for obj in queryset:
            tasks.update_character_section.apply_async(
                kwargs={"character_pk": obj.pk, "section": section},
                priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY,
            )  # type: ignore
            self.message_user(
                request,
                _("Started updating section %(section)s for character %(character)s.")
                % {
                    "section": Character.UpdateSection.display_name(section),
                    "character": obj,
                },
            )

    @admin.display(
        description=_("Update %s for selected characters from EVE server")
        % Character.UpdateSection.display_name(Character.UpdateSection.ONLINE_STATUS)
    )
    def update_online_status(self, request, queryset):
        section = Character.UpdateSection.ONLINE_STATUS
        for obj in queryset:
            tasks.update_character_section.apply_async(
                kwargs={"character_pk": obj.pk, "section": section},
                priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY,
            )  # type: ignore
            self.message_user(
                request,
                _(
                    "Started updating %(section)s for character %(character)s."
                    % {
                        "section": Character.UpdateSection.display_name(section),
                        "character": obj,
                    }
                ),
            )

    @admin.display(description=_("Enable selected characters"))
    def enable_characters(self, request, queryset):
        pks = list(queryset.values_list("pk", flat=True))
        queryset.filter(pk__in=pks).update(is_disabled=False)
        self.message_user(request, _("Enabled %d characters.") % len(pks))

    @admin.display(description=_("Disable selected characters"))
    def disable_characters(self, request, queryset):
        pks = list(queryset.values_list("pk", flat=True))
        queryset.filter(pk__in=pks).update(is_disabled=True)
        self.message_user(request, _("Disabled %d characters.") % len(pks))

    inlines = (SyncStatusAdminInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("id", "_name", "_type", "_group", "_solar_system", "_updated_at")
    list_filter = (
        ("eve_type__eve_group__eve_category", admin.RelatedOnlyFieldListFilter),
        ("eve_type__eve_group", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = [
        "id",
        "name",
        "eve_solar_system__eve_constellation__eve_region__name",
        "eve_type__name",
    ]
    list_select_related = (
        "eve_type__eve_group",
        "eve_type",
        "eve_solar_system__eve_constellation__eve_region",
        "eve_solar_system",
    )
    ordering = ["id"]

    @admin.display(ordering="name", description=_("name"))
    def _name(self, obj):
        return obj.name_plus

    @admin.display(ordering="eve_solar_system__name", description=_("solar system"))
    def _solar_system(self, obj):
        return obj.eve_solar_system.name if obj.eve_solar_system else None

    @admin.display(ordering="eve_type__name", description=_("type"))
    def _type(self, obj):
        return obj.eve_type.name if obj.eve_type else None

    @admin.display(ordering="eve_type__eve_group__name", description=_("group"))
    def _group(self, obj):
        return obj.eve_type.eve_group.name if obj.eve_type else None

    @admin.display(ordering="updated_at", description=_("updated at"))
    def _updated_at(self, obj):
        return obj.name_plus

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SkillSetGroup)
class SkillSetGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "_skill_sets", "is_doctrine", "is_active")
    list_filter = (
        "is_doctrine",
        "is_active",
        ("skill_sets", admin.RelatedOnlyFieldListFilter),
    )
    ordering = ["name"]
    filter_horizontal = ("skill_sets",)
    readonly_fields = ("last_modified_at", "last_modified_by")
    fields = [
        "name",
        "description",
        "skill_sets",
        "is_doctrine",
        "is_active",
        ("last_modified_at", "last_modified_by"),
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related(
            Prefetch(
                "skill_sets",
                queryset=SkillSet.objects.order_by("name"),
                to_attr="skill_sets_ordered",
            )
        )

    def _skill_sets(self, obj):
        return format_html("<br>".join([x.name for x in obj.skill_sets_ordered]))

    def save_model(self, request, obj, form, change):
        obj.last_modified_by = request.user
        obj.last_modified_at = now()
        super().save_model(request, obj, form, change)


class MinValidatedInlineMixIn:
    validate_min = True

    def get_formset(self, *args, **kwargs):
        return super().get_formset(validate_min=self.validate_min, *args, **kwargs)


class SkillSetSkillAdminFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in self.forms:
            try:
                data = self.cleaned_data
            except AttributeError:
                pass
            else:
                for row in data:
                    if (
                        row
                        and row.get("DELETE") is False
                        and not row.get("required_level")
                        and not row.get("recommended_level")
                    ):
                        eve_type = row.get("eve_type")
                        raise ValidationError(
                            _("Skill '%s' must have a level.") % eve_type.name
                        )


class SkillSetSkillAdminInline(MinValidatedInlineMixIn, admin.TabularInline):
    model = SkillSetSkill
    verbose_name = "skill"
    verbose_name_plural = "skills"
    min_num = 1
    formset = SkillSetSkillAdminFormSet
    autocomplete_fields = ("eve_type",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("eve_type", "skill_set__ship_type")

    # def get_formset(self, *args, **kwargs):
    #     formset = super().get_formset(*args, **kwargs)
    #     qs = formset.form.base_fields["skill_set"].queryset
    #     qs = qs.select_related("skill_set__ship_type__eve_group")
    #     formset.form.base_fields["skill_set"].queryset = qs
    #     return formset


# class SkillSetShipTypeFilter(admin.SimpleListFilter):
#     title = "is ship type"
#     parameter_name = "is_ship_type"

#     def lookups(self, request, model_admin):
#         return (
#             ("yes", "yes"),
#             ("no", "no"),
#         )

#     def queryset(self, request, queryset):
#         if self.value() == "yes":
#             return SkillSet.objects.filter(ship_type__isnull=False)
#         if self.value() == "no":
#             return SkillSet.objects.filter(ship_type__isnull=True)
#         return SkillSet.objects.all()


@admin.register(SkillSet)
class SkillSetAdmin(admin.ModelAdmin):
    autocomplete_fields = ("ship_type",)
    list_display = (
        "name",
        "ship_type",
        "_skills",
        "_groups",
        "is_visible",
    )
    list_filter = (
        # SkillSetShipTypeFilter,  # this filter disables the prefetch in get_queryset
        ("groups", admin.RelatedOnlyFieldListFilter),
        "is_visible",
    )
    ordering = ["name"]
    search_fields = ["name"]

    fields = [
        "name",
        "description",
        "ship_type",
        "is_visible",
        ("last_modified_at", "last_modified_by"),
    ]
    readonly_fields = ("last_modified_at", "last_modified_by")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("ship_type").prefetch_related(
            Prefetch(
                "skills",
                queryset=SkillSetSkill.objects.select_related("eve_type").order_by(
                    "eve_type__name"
                ),
                to_attr="skills_ordered",
            ),
            Prefetch(
                "groups",
                queryset=SkillSetGroup.objects.order_by("name"),
                to_attr="groups_ordered",
            ),
        )

    def _skills(self, obj):
        return [
            "{} {} {}".format(
                skill.eve_type.name,
                skill.required_level if skill.required_level else "",
                f"[{skill.recommended_level}]" if skill.recommended_level else "",
            )
            for skill in obj.skills_ordered
        ]

    def _groups(self, obj) -> Optional[List[str]]:
        groups = [f"{group.name}" for group in obj.groups_ordered]
        return groups if groups else None

    inlines = (SkillSetSkillAdminInline,)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "ship_type":
            kwargs["queryset"] = (
                EveType.objects.select_related("eve_group__eve_category")
                .filter(eve_group__eve_category=EveCategoryId.SHIP)
                .order_by("name")
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        obj.user = request.user
        obj.last_modified_by = request.user
        obj.last_modified_at = now()
        super().save_model(request, obj, form, change)
        tasks.update_characters_skill_checks.apply_async(
            kwargs={"force_update": True}, priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY
        )  # type: ignore

    def delete_model(self, request, obj):
        obj.user = request.user
        super().delete_model(request, obj)
        tasks.update_characters_skill_checks.apply_async(
            kwargs={"force_update": True}, priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY
        )  # type: ignore
