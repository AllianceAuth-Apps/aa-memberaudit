"""Return current statistics about Member Audit."""

import datetime as dt
import logging

from tqdm import tqdm

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, F, Max, Min

from app_utils.logging import LoggerAddTag

from memberaudit import __title__, app_settings
from memberaudit.constants import IS_TESTING
from memberaudit.helpers import character_section_models
from memberaudit.management.commands._helpers import Table
from memberaudit.models import Character, CharacterUpdateStatus, characters

from . import get_input

logger = LoggerAddTag(logging.getLogger(__name__), __title__)


class Command(BaseCommand):
    help = str(__doc__)

    def handle(self, *args, **options):
        self.stdout.write("1 - Settings")
        self.stdout.write("2 - Object counts")
        self.stdout.write("3 - Stale minutes")
        self.stdout.write("4 - Update statistics")

        result = get_input("Enter 1 - 4 to choose a menu or any other input to exit? ")
        self.stdout.write("")

        if result not in ["1", "2", "3", "4"]:
            self.stdout.write(self.style.WARNING("Aborted"))

        if result == "1":
            data = _fetch_settings()
            self._output_section(data, "settings")

        elif result == "2":
            data = _calc_object_counts()
            self._output_section(data, "object counts", "right")

        elif result == "3":
            data = _fetch_stale_minutes()
            self._output_section(data, "stale minutes", "right")

        elif result == "4":
            self.stdout.write("Calculating...\r", ending="")
            data = _calc_update_stats()

            self._write_title("update statistic")
            table = Table(default_alignment=Table.Alignment.RIGHT)
            table.set_data(data)
            table.set_alignment(0, Table.Alignment.LEFT)
            table.write(self.stdout)

    def _write_title(self, text: str):
        output = text.title()
        self.stdout.write(self.style.SUCCESS(f"{output:<20}"))
        self.stdout.write("")

    def _output_section(self, data: dict, title: str, alignment: str = "left"):
        self._write_title(title)

        if alignment == "left":
            alignment_symbol = "<"
        elif alignment == "right":
            alignment_symbol = ">"
        else:
            raise NotImplementedError(f"Unknown alignment: {alignment}")

        data_sorted = dict(sorted(data.items()))
        data_formatted = {
            label: self._format_value(value) for label, value in data_sorted.items()
        }
        label_width = max(len(label) for label in data_formatted) + 1
        value_width = max(len(value) for value in data_formatted.values()) + 1

        for label, value in data_formatted.items():
            self.stdout.write(
                f"  {label:<{label_width}}: {value:{alignment_symbol}{value_width}}"
            )

    def _format_value(self, value):
        return f"{value:,}" if isinstance(value, (int, float)) else str(value)


def _fetch_stale_minutes():
    return dict(characters.section_time_until_stale)


def _calc_object_counts():
    work = []
    for model_class in character_section_models():
        name = str(model_class._meta.verbose_name_plural)
        query = model_class.objects.all()
        work.append((name, query))

    characters_enabled = Character.objects.filter(is_disabled=False)
    work.append(("characters enabled", characters_enabled))

    user_query = User.objects.filter(
        character_ownerships__character__memberaudit_character__isnull=False
    ).distinct()
    work.append(("users with access", user_query))

    object_counts = {
        name: query.count()
        for name, query, in tqdm(
            work, desc="Calculating object counts", leave=False, disable=IS_TESTING
        )
    }
    return object_counts


def _calc_update_stats():
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
