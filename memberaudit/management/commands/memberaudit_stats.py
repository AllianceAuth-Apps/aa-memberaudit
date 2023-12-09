"""Return current statistics about Member Audit."""

import datetime as dt
import logging

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, F, Max, Min

from app_utils.logging import LoggerAddTag

from memberaudit import __title__, app_settings
from memberaudit.helpers import character_section_models
from memberaudit.management.commands._helpers import Table
from memberaudit.models import Character, CharacterUpdateStatus, characters

logger = LoggerAddTag(logging.getLogger(__name__), __title__)


class Command(BaseCommand):
    help = str(__doc__)

    def handle(self, *args, **options):
        stats = self._calc_statistics()
        self._output_section(stats["settings"], "settings")
        self.stdout.write("")

        self._output_section(stats["object_counts"], "object counts")
        self.stdout.write("")
        self.stdout.write("")

        self._output_section(stats["stale_minutes"], "stale minutes")
        self.stdout.write("")

        self._write_title("sections")
        table = Table(default_alignment=Table.Alignment.RIGHT)
        table.set_data(stats["sections"])
        table.set_alignment(0, Table.Alignment.LEFT)
        table.write(self.stdout)
        self.stdout.write("")
        self.stdout.write("")

    def _calc_statistics(self) -> dict:
        """Return detailed statistics about Member Audit."""

        work = [
            ("settings", _fetch_settings, False),
            ("stale_minutes", _fetch_stale_minutes, False),
            ("object_counts", _calc_object_counts, True),
            ("sections", _calc_sections, True),
        ]

        data = {}
        for key, func, is_slow in work:
            if is_slow:
                self.stdout.write(f"Calculating {key.replace('_', ' ')}...")

            data[key] = func()

        return data

    def _write_title(self, text: str):
        self.stdout.write(self.style.SUCCESS(f"{text.title()}:"))
        self.stdout.write("")

    def _output_section(self, data: dict, title: str):
        self._write_title(title)
        max_width = max(len(label) for label in data) + 1
        data_sorted = dict(sorted(data.items()))
        for label, value in data_sorted.items():
            value_str = f"{value:,}" if isinstance(value, (int, float)) else value
            self.stdout.write(f"  {label: <{max_width}}: {value_str}")


def _fetch_stale_minutes():
    return dict(characters.section_time_until_stale)


def _calc_object_counts():
    object_counts = {}
    for model_class in character_section_models():
        name = str(model_class._meta.verbose_name_plural)
        count = model_class.objects.count()
        object_counts[name] = count

    user_count = (
        User.objects.filter(
            character_ownerships__character__memberaudit_character__isnull=False
        )
        .distinct()
        .count()
    )
    object_counts["users with access"] = user_count
    return object_counts


def _calc_sections():
    sections = {section: {"section": section} for section in Character.UpdateSection}

    durations = (
        CharacterUpdateStatus.objects.filter(
            is_success=True,
            update_started_at__isnull=False,
            update_finished_at__isnull=False,
        )
        .annotate(duration=F("update_finished_at") - F("update_started_at"))
        .values("section")
        .annotate(duration_min=Min("duration"))
        .annotate(duration_avg=Avg("duration"))
        .annotate(duration_max=Max("duration"))
        .annotate(sample_size=Count("pk"))
        .values(
            "section", "duration_min", "duration_avg", "duration_max", "sample_size"
        )
    )
    durations_mapped = {
        Character.UpdateSection(obj["section"]): obj for obj in durations
    }

    duration_fields = ("duration_min", "duration_avg", "duration_max", "sample_size")
    for section in sections:
        try:
            obj = durations_mapped[section]
        except KeyError:
            section_durations = {field: None for field in duration_fields}
        else:
            section_durations = {
                field: _convert_timedelta(obj[field]) for field in duration_fields
            }

        sections[section].update(section_durations)

    return list(sections.values())


def _convert_timedelta(value):
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    return value


def _fetch_settings():
    settings = {
        name: value
        for name, value in vars(app_settings).items()
        if name.startswith("MEMBERAUDIT_")
        and name
        not in {
            "MEMBERAUDIT_BASE_URL",
            "MEMBERAUDIT_SECTION_STALE_MINUTES_SECTION_DEFAULTS",
        }
    }
    return settings
