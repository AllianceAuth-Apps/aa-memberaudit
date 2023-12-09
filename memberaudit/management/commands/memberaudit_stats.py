"""Return current statistics about Member Audit."""

import datetime as dt
import logging
from enum import Enum
from typing import Any, Dict, List, Tuple, Union

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management.base import BaseCommand, OutputWrapper
from django.db.models import Avg, Count, F, Max, Min

from app_utils.logging import LoggerAddTag

from memberaudit import __title__, app_settings
from memberaudit.helpers import character_section_models
from memberaudit.models import Character, CharacterUpdateStatus, characters

logger = LoggerAddTag(logging.getLogger(__name__), __title__)

_CACHE_TIMEOUT = 3600
_CACHE_KEY = "memberaudit-stats"


class Command(BaseCommand):
    help = str(__doc__)

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear-cache",
            action="store_true",
            help="Clear the cache for this command",
        )

    def handle(self, *args, **options):
        if options["clear_cache"]:
            clear_cache()

        stats = self._calc_statistics()

        self._write_title("sections")
        table = Table(default_alignment=Table.Alignment.RIGHT)
        table.set_data(stats["sections"])
        table.set_alignment(0, Table.Alignment.LEFT)
        table.write(self.stdout)
        self.stdout.write("")
        self.stdout.write("")

        self._output_section(stats["object_counts"], "object counts")
        self.stdout.write("")
        self.stdout.write("")

        self._output_section(stats["settings"], "settings")
        self.stdout.write("")

    def _calc_statistics(self) -> dict:
        """Return detailed statistics about Member Audit."""

        work = [
            ("settings", _fetch_settings, False),
            ("sections", _calc_sections, True),
            ("object_counts", _calc_object_counts, True),
        ]

        data = {}
        for key, func, can_cache in work:
            if can_cache:
                self.stdout.write(f"Calculating {key.replace('_', ' ')}...")
                cache_key = f"{_CACHE_KEY}-{key}"
                data[key] = cache.get_or_set(
                    key=cache_key, default=func, timeout=_CACHE_TIMEOUT
                )
            else:
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


class Table:
    """A class for rendering a table on the terminal."""

    class Alignment(str, Enum):
        """An alignment of a column."""

        LEFT = "left"
        RIGHT = "right"

        @property
        def to_f(self) -> str:
            """Return as symbol for f-strings"""
            if self is self.LEFT:
                return "<"

            if self is self.RIGHT:
                return ">"

            raise NotImplementedError("Invalid alignment")

    def __init__(self, default_alignment="left") -> None:
        self._rows: List[Tuple[str, ...]] = []
        self._column_width: Tuple[int, ...] = tuple()
        self._alignment: List[Table.Alignment] = []
        self._default_alignment = self.Alignment(default_alignment)

    def set_data(self, data: List[Dict[str, Any]]):
        """Set data of this table."""
        self._rows = self._convert_to_table(data)
        self._column_widths = self._calculate_column_width()
        self._reset_alignment()

    @property
    def columns_count(self) -> int:
        """Return number of columns."""
        return len(self._rows[0])

    def _convert_to_table(self, data: List[dict]) -> List[Tuple[str, ...]]:
        table = [tuple(self._format_head(v) for v in data[0].keys())]
        table += [tuple(self._format_value(v) for v in o.values()) for o in data]
        return table

    def _format_head(self, value: str) -> str:
        return value.replace("_", " ").capitalize()

    def _format_value(self, value) -> str:
        if value is None:
            return "?"

        if isinstance(value, float):
            return f"{value:,.1f}"

        if isinstance(value, int):
            return f"{value:,}"

        return str(value)

    def _calculate_column_width(self) -> Tuple[int, ...]:
        widths = [[] for _ in self._rows[0]]
        for row in self._rows:
            for col_num, column in enumerate(row):
                widths[col_num].append(len(column))

        max_width = tuple(max(column) for column in widths)
        return max_width

    def _reset_alignment(self):
        self._alignment = [self._default_alignment for _ in range(self.columns_count)]

    def set_alignment(self, column: int, alignment: Union[Alignment, str]):
        """Set alignment for a column."""
        self._alignment[column] = alignment

    def write(self, stdout: OutputWrapper, indentation: int = 2, margin: int = 2):
        """Write table to output."""
        self._write_table(stdout, indentation, margin)

    def _write_table(self, stdout: OutputWrapper, indentation: int, margin: int):
        columns_count = self.columns_count
        for row_num, row in enumerate(self._rows):
            output_row = " " * indentation
            for col_num, column in enumerate(row):
                width = self._column_widths[col_num]
                alignment = self._alignment[col_num]
                output_row += f"{column:{alignment.to_f}{width}}"

                if col_num < columns_count - 1:
                    output_row += " " * margin

            stdout.write(output_row)

            if row_num == 0:
                output_row = " " * indentation
                for col_num, _ in enumerate(row):
                    width = self._column_widths[col_num]
                    output_row += "-" * width + " " * margin
                stdout.write(output_row)


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
    stale_minutes = dict(characters.section_time_until_stale)
    sections = {
        section: {"section": section, "stale_minutes": minutes}
        for section, minutes in stale_minutes.items()
    }

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


def clear_cache():
    """Delete the cache used by this command."""
    cache.delete_pattern(f"{_CACHE_KEY}*")
