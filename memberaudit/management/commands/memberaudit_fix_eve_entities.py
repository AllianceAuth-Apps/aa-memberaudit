"""Deleting all unresolved and orphaned EveEntities.

This tool was written to remove invalid EveEntities created by a bug (see issue #156).
"""

from tqdm import tqdm

from django.contrib.admin.utils import NestedObjects
from django.core.management.base import BaseCommand, CommandParser
from django.db import DatabaseError
from django.db.models import QuerySet
from eveuniverse.models import EveEntity

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.constants import IS_TESTING

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class Command(BaseCommand):
    help = str(__doc__)

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--no-input", "--noinput", action="store_true", help="Skip all user input"
        )

    def handle(self, *args, **options):
        objs_to_delete = _gather_objs_to_delete()
        to_delete_count = objs_to_delete.count()

        if not to_delete_count:
            self.stdout.write(
                self.style.SUCCESS(
                    "No matching EveEntity objects found. No fix required."
                )
            )
            return

        response = self._ask_user(options, to_delete_count)
        if response.lower() == "n":
            self.stdout.write(self.style.WARNING("Aborted"))
            return

        deleted_count, error_count = _delete_objects(objs_to_delete)

        if error_count:
            self.stdout.write(
                self.style.WARNING(
                    f"{error_count} EveEntity objects could not be deleted. "
                    "See extension log for details."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted_count} EveEntity objects.")
        )

    def _ask_user(self, options, to_delete_count) -> str:
        if options["no_input"]:
            return "y"

        self.stdout.write(
            f"Found {to_delete_count} unresolved and orphaned EveEntity objects, "
            "which can be safely removed."
        )
        self.stdout.write("Do you want to delete these objects? ", ending="")
        response = input("(Y/n)")
        return response


def _gather_objs_to_delete() -> QuerySet:
    objs = EveEntity.objects.filter(name="", category=None)
    if not objs.exists():
        return EveEntity.objects.none()

    to_delete_ids = []
    objs_with_progress_bar = tqdm(
        objs,
        desc="Checking relations",
        total=objs.count(),
        disable=IS_TESTING,
        leave=False,
    )
    for obj in objs_with_progress_bar:
        collector = NestedObjects(using="default")
        collector.collect([obj])
        related_model_count = collector.data.keys()
        if len(related_model_count) == 1:
            to_delete_ids.append(obj.id)

    return EveEntity.objects.filter(id__in=to_delete_ids)


def _delete_objects(objs_to_delete: QuerySet[EveEntity]) -> int:
    error_count = 0
    deleted_count = 0
    objs_with_progress_bar = tqdm(
        objs_to_delete,
        desc="Deleting objects",
        total=objs_to_delete.count(),
        leave=False,
        disable=IS_TESTING,
    )
    for obj in objs_with_progress_bar:
        try:
            obj.delete()
        except DatabaseError:
            logger.exception("Failed to delete EveEntity object with ID %d", obj.id)
            error_count += 1
        else:
            deleted_count += 1

    logger.info("Deleted %d EveEntity objects.", deleted_count)
    return deleted_count, error_count
