"""Return current statistics about Member Audit."""

import logging

from django.apps import apps
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from app_utils.logging import LoggerAddTag

from memberaudit import __title__, app_settings

logger = LoggerAddTag(logging.getLogger(__name__), __title__)


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **options):
        stats = calc_statistics()

        self._output_section(stats["object_counts"], "Object counts")
        self.stdout.write("")
        self._output_section(stats["settings"], "Settings")

    def _output_section(self, data: dict, title: str):
        self.stdout.write(f"{title}:")
        max_width = max(len(label) for label in data) + 1
        data_sorted = dict(sorted(data.items()))
        for label, value in data_sorted.items():
            value_str = f"{value:,}" if isinstance(value, (int, float)) else value
            self.stdout.write(f"  {label: <{max_width}}: {value_str}")


def calc_statistics() -> dict:
    """Return detailed statistics about Member Audit."""

    object_counts = {}
    my_app = apps.get_app_config("memberaudit")
    my_character_models = [
        model_class
        for model_class in my_app.get_models()
        if model_class.__name__.startswith("Character")
    ]
    for model_class in my_character_models:
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
    data = {"object_counts": object_counts, "settings": _fetch_settings()}

    return data


def _fetch_settings():
    settings = {
        name: value
        for name, value in vars(app_settings).items()
        if name.startswith("MEMBERAUDIT_")
    }
    return settings
