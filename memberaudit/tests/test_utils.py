from unittest.mock import patch

from django.contrib.auth.models import Group
from eveuniverse.models import EveEntity

from app_utils.testdata_factories import (
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserMainFactory,
)
from app_utils.testing import NoSocketsTestCase

from memberaudit.tests.testdata.factories_2 import GroupFactory, StateFactory
from memberaudit.utils import (
    clear_users_from_group,
    filter_groups_available_to_user,
    get_or_create_esi_or_none,
    get_or_create_or_none,
    get_or_none,
    get_unidecoded_slug,
)


class TestFilterGroupsAvailableToUser(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.corporation = EveCorporationInfoFactory()
        cls.my_state = StateFactory(member_corporations=[cls.corporation], priority=200)
        cls.normal_group = GroupFactory()
        cls.state_group = GroupFactory(authgroup__states=[cls.my_state])

    def test_should_include_state_group_for_members(self):
        # given
        user = UserMainFactory(
            main_character__character=EveCharacterFactory(corporation=self.corporation)
        )

        # when
        got = filter_groups_available_to_user(Group.objects.all(), user)

        # then
        want = [self.normal_group, self.state_group]
        self.assertCountEqual(got, want)

    def test_should_not_include_state_group_for_non_members(self):
        # given
        user = UserMainFactory()

        # when
        got = filter_groups_available_to_user(Group.objects.all(), user)

        # then
        want = [self.normal_group]
        self.assertCountEqual(got, want)


class TestClearUsersFromGroup(NoSocketsTestCase):
    def test_should_clear_users_from_group(self):
        # given
        group_1 = GroupFactory()
        group_2 = GroupFactory()
        user_1 = UserMainFactory()
        user_1.groups.add(group_1, group_2)
        user_2 = UserMainFactory()
        user_2.groups.add(group_1, group_2)

        # when
        clear_users_from_group(group_1)

        # then
        self.assertCountEqual(user_1.groups.all(), [group_2])
        self.assertCountEqual(user_2.groups.all(), [group_2])


class TestGetUnidecodedSlug(NoSocketsTestCase):
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


class TestGetOrCreateOrNone(NoSocketsTestCase):
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


class TestGetOrNone(NoSocketsTestCase):
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
