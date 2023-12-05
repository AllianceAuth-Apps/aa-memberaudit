from unittest.mock import patch

from django.contrib.auth.models import Group
from django.db import models
from django.test import TestCase
from eveuniverse.models import EveEntity

from allianceauth.eveonline.models import EveCorporationInfo
from app_utils.testing import (
    NoSocketsTestCase,
    create_authgroup,
    create_state,
    create_user_from_evecharacter,
)

from memberaudit.utils import (
    clear_users_from_group,
    filter_groups_available_to_user,
    get_or_create_esi_or_none,
    get_or_create_or_none,
    get_or_none,
    get_unidecoded_slug,
)

from .testdata.load_entities import load_entities

MODULE_PATH = "memberaudit.utils"


def querysets_pks(qs1: models.QuerySet, qs2: models.QuerySet) -> tuple:
    """Two querysets as set of pks for comparison with assertSetEqual()."""
    qs1_pks = set(qs1.values_list("pk", flat=True))
    qs2_pks = set(qs2.values_list("pk", flat=True))
    return (qs1_pks, qs2_pks)


class TestHelpers(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()
        member_corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        cls.my_state = create_state(
            member_corporations=[member_corporation], priority=200
        )
        cls.normal_group = create_authgroup()
        cls.state_group = create_authgroup(states=[cls.my_state])

    def test_should_include_state_group_for_members(self):
        # given
        user, _ = create_user_from_evecharacter(1001)  # in member corporation
        # when
        result_qs = filter_groups_available_to_user(Group.objects.all(), user)
        # then
        self.assertSetEqual(
            *querysets_pks(
                Group.objects.filter(
                    pk__in=[self.normal_group.pk, self.state_group.pk]
                ),
                result_qs,
            )
        )

    def test_should_not_include_state_group_for_non_members(self):
        # given
        user, _ = create_user_from_evecharacter(1101)  # not in member corporation
        # when
        result_qs = filter_groups_available_to_user(Group.objects.all(), user)
        # then
        self.assertSetEqual(
            *querysets_pks(
                Group.objects.filter(pk__in=[self.normal_group.pk]), result_qs
            )
        )

    def test_should_clear_users_from_group(self):
        # given
        group_1 = create_authgroup()
        group_2 = create_authgroup()
        user_1001, _ = create_user_from_evecharacter(1001)
        user_1001.groups.add(group_1, group_2)
        user_1002, _ = create_user_from_evecharacter(1002)
        user_1002.groups.add(group_1, group_2)
        # when
        clear_users_from_group(group_1)
        # then
        self.assertSetEqual(
            {group_2.pk}, set(user_1001.groups.values_list("pk", flat=True))
        )
        self.assertSetEqual(
            {group_2.pk}, set(user_1002.groups.values_list("pk", flat=True))
        )

    def test_get_unidecoded_slug_with_default_app_name(self):
        """Test get_unidecoded_slug with default app name"""

        # given
        app_name = "Member Audit"

        # when
        app_url_slug = get_unidecoded_slug(app_name)

        # then
        expected_app_url_slug = "member-audit"
        self.assertEqual(app_url_slug, expected_app_url_slug)

    def test_get_unidecoded_slug_with_no_app_name(self):
        """Test get_unidecoded_slug with no app name"""

        # when
        app_url_slug = get_unidecoded_slug()

        # then
        expected_app_url_slug = "member-audit"
        self.assertEqual(app_url_slug, expected_app_url_slug)

    def test_get_unidecoded_slug_with_custom_app_name(self):
        """Test get_unidecoded_slug with custom app name"""

        # given
        app_name = "これが監査です"

        # when
        app_url_slug = get_unidecoded_slug(app_name)

        # then
        expected_app_url_slug = "koregajian-cha-desu"
        self.assertEqual(app_url_slug, expected_app_url_slug)


class TestGetOrCreateEsiOrNone(NoSocketsTestCase):
    def test_should_get_and_return_obj_when_it_exists(self):
        # given
        obj = EveEntity.objects.create(
            id=42, name="dummy", category=EveEntity.CATEGORY_CHARACTER
        )
        # when
        result = get_or_create_esi_or_none(
            "character_id", {"character_id": 42}, EveEntity
        )
        # then
        self.assertEqual(obj, result)

    def test_should_create_and_return_obj_when_it_exists(self):
        def my_func(*args, **kwargs):
            obj = EveEntity.objects.create(
                id=42, name="dummy", category=EveEntity.CATEGORY_CHARACTER
            )
            return obj, True

        # when
        with patch.object(EveEntity.objects, "get_or_create_esi") as mock:
            mock.side_effect = my_func
            result = get_or_create_esi_or_none(
                "character_id", {"character_id": 42}, EveEntity
            )
        # then
        self.assertEqual(result.id, 42)

    def test_should_return_none_when_obj_can_not_be_found(self):
        cases = [
            ("unknown", {"character_id": 42}),
            ("character_id", {"character_id": None}),
            ("character_id", {}),
        ]
        for num, (prop_name, dct) in enumerate(cases):
            with self.subTest(num=num):
                # when
                result = get_or_create_esi_or_none(prop_name, dct, EveEntity)
                # then
                self.assertIsNone(result)


class TestGetOrCreateOrNone(TestCase):
    def test_should_get_and_return_obj_when_it_exists(self):
        # given
        obj = EveEntity.objects.create(id=42)
        # when
        result = get_or_create_or_none("character_id", {"character_id": 42}, EveEntity)
        # then
        self.assertEqual(obj, result)

    def test_should_create_and_return_obj_when_it_exists(self):
        # when
        result = get_or_create_or_none("character_id", {"character_id": 42}, EveEntity)
        # then
        self.assertEqual(result.id, 42)

    def test_should_return_none_when_obj_can_not_be_found(self):
        cases = [
            ("unknown", {"character_id": 42}),
            ("character_id", {"character_id": None}),
            ("character_id", {}),
        ]
        for num, (prop_name, dct) in enumerate(cases):
            with self.subTest(num=num):
                # when
                result = get_or_create_or_none(prop_name, dct, EveEntity)
                # then
                self.assertIsNone(result)


class TestGetOrNone(TestCase):
    def test_should_return_obj_when_it_exists(self):
        # given
        obj = EveEntity.objects.create(id=42)
        # when
        result = get_or_none("character_id", {"character_id": 42}, EveEntity)
        # then
        self.assertEqual(obj, result)

    def test_should_return_none_when_obj_can_not_be_found(self):
        cases = [
            ("unknown", {"character_id": 42}),
            ("character_id", {"character_id": None}),
            ("character_id", {"character_id": 42}),
            ("character_id", {}),
        ]
        for num, (prop_name, dct) in enumerate(cases):
            with self.subTest(num=num):
                # when
                result = get_or_none(prop_name, dct, EveEntity)
                # then
                self.assertIsNone(result)
