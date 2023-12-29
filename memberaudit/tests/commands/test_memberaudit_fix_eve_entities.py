from io import StringIO
from typing import Set
from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase
from eveuniverse.models import EveEntity

from app_utils.testing import create_fake_user

from memberaudit.tests.testdata.factories import (
    create_character,
    create_character_contact,
)

MODULE_PATH = "memberaudit.management.commands.memberaudit_fix_eve_entities"


class TestDeleteUnresolved(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user = create_fake_user(1001, "Bruce Wayne")
        cls.character = create_character(user.profile.main_character)

    def test_should_remove_unresolved_and_orphaned_only(self):
        # given
        EveEntity.objects.create(id=1)
        EveEntity.objects.create(
            id=1001, name="Bruce Wayne", category=EveEntity.CATEGORY_CHARACTER
        )
        contact = EveEntity.objects.create(id=2)
        create_character_contact(self.character, eve_entity=contact)

        # when
        call_command("memberaudit_fix_eve_entities", "--no-input", stdout=StringIO())

        # then
        expected = _fetch_eve_entity_ids()
        self.assertSetEqual(expected, {2, 1001})

    def test_should_skip_over_database_errors(self):
        # given
        EveEntity.objects.create(id=1)

        # when
        with patch(MODULE_PATH + ".EveEntity.delete") as mock:
            mock.side_effect = IntegrityError
            call_command(
                "memberaudit_fix_eve_entities", "--no-input", stdout=StringIO()
            )

        # then
        expected = _fetch_eve_entity_ids()
        self.assertSetEqual(expected, {1})

    def test_should_not_skip_over_other_errors(self):
        # given
        EveEntity.objects.create(id=1)

        # when
        with self.assertRaises(RuntimeError):
            with patch(MODULE_PATH + ".EveEntity.delete") as mock:
                mock.side_effect = RuntimeError
                call_command(
                    "memberaudit_fix_eve_entities", "--no-input", stdout=StringIO()
                )

        expected = _fetch_eve_entity_ids()
        self.assertSetEqual(expected, {1})


def _fetch_eve_entity_ids() -> Set[int]:
    return set(EveEntity.objects.values_list("id", flat=True))
