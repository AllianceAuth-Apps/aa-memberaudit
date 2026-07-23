from django.core.exceptions import ValidationError
from eveuniverse.tests.testdata.factories_2 import EveTypeFactory

from app_utils.testdata_factories import (
    EveAllianceInfoFactory,
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserMainFactory,
)
from app_utils.testing import NoSocketsTestCase, add_character_to_user

from memberaudit.constants import SKILL_SET_DEFAULT_ICON_TYPE_ID
from memberaudit.models import (
    ComplianceGroupDesignation,
    EveShipType,
    EveSkillType,
    General,
    Location,
    MailEntity,
    SkillSet,
    SkillSetGroup,
    SkillSetSkill,
)
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    GroupFactory,
    LocationAssetSafetyFactory,
    LocationSolarSystemFactory,
    LocationStationFactory,
    LocationStructureFactory,
    LocationUnknownFactory,
    MailEntityAllianceFactory,
    MailEntityCharacterFactory,
    MailEntityCorporationFactory,
    MailEntityMailingListFactory,
    NavigationSkillTypeFactory,
    SkillSetFactory,
    SkillSetSkillFactory,
    UserMainBasicAccessFactory,
)
from memberaudit.tests.utils import permissions_for_model


class TestMailEntity(NoSocketsTestCase):
    def test_str(self):
        obj = MailEntityCharacterFactory(name="Bruce Wayne")
        self.assertEqual(str(obj), "Bruce Wayne")

    def test_eve_entity_categories(self):
        obj = MailEntityCharacterFactory()
        self.assertSetEqual(
            obj.eve_entity_categories,
            {
                MailEntity.Category.ALLIANCE,
                MailEntity.Category.CHARACTER,
                MailEntity.Category.CORPORATION,
            },
        )

    def test_name_plus_1(self):
        obj = MailEntityCharacterFactory(name="Bruce Wayne")
        self.assertEqual(obj.name_plus, "Bruce Wayne")

    def test_name_plus_2(self):
        obj = MailEntity.objects.create(id=42, category=MailEntity.Category.ALLIANCE)
        self.assertEqual(obj.name_plus, "Alliance #42")

    def test_need_to_specify_category(self):
        with self.assertRaises(ValidationError):
            MailEntity.objects.create(id=1)

    def test_url_1(self):
        obj = MailEntityAllianceFactory()
        self.assertIn("dotlan", obj.external_url())

    def test_url_2(self):
        obj = MailEntityCorporationFactory()
        self.assertIn("dotlan", obj.external_url())

    def test_url_3(self):
        obj = MailEntityCharacterFactory()
        self.assertIn("evewho", obj.external_url())

    def test_url_4(self):
        obj = MailEntityMailingListFactory()
        self.assertEqual(obj.external_url(), "")

    def test_url_5(self):
        obj = MailEntity.objects.create(id=9887, category=MailEntity.Category.ALLIANCE)
        self.assertEqual(obj.external_url(), "")

    def test_url_6(self):
        obj = MailEntity.objects.create(
            id=9887, category=MailEntity.Category.CORPORATION
        )
        self.assertEqual(obj.external_url(), "")


class TestGeneralOther(NoSocketsTestCase):
    def test_should_return_compliant_users_only(self):
        # given

        user_compliant = UserMainBasicAccessFactory()
        CharacterFactory(user=user_compliant)
        CharacterFactory(user=user_compliant, is_main=False)

        user_non_compliant = UserMainBasicAccessFactory()
        CharacterFactory(user=user_non_compliant)
        add_character_to_user(user=user_non_compliant, character=EveCharacterFactory())

        user_no_access = UserMainFactory()
        CharacterFactory(user=user_no_access)

        # when
        got = General.compliant_users()

        # then
        self.assertCountEqual(got, [user_compliant])

    def test_should_add_group_to_compliant_user_only(self):
        # given
        user_compliant = UserMainBasicAccessFactory()
        CharacterFactory(user=user_compliant)

        user_non_compliant = UserMainBasicAccessFactory()
        add_character_to_user(user=user_non_compliant, character=EveCharacterFactory())

        group = GroupFactory(authgroup__internal=True)

        # when
        General.add_compliant_users_to_group(group)

        # then
        self.assertIn(group, user_compliant.groups.all())
        self.assertNotIn(group, user_non_compliant.groups.all())


class TestGeneral_AccessibleUsers(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        alliance = EveAllianceInfoFactory()
        cls.corporation = EveCorporationInfoFactory(alliance=alliance)
        cls.user_same_corporation = UserMainFactory(
            permissions__=["memberaudit.basic_access"],
            main_character__character=EveCharacterFactory(corporation=cls.corporation),
        )
        cls.user_same_alliance = UserMainFactory(
            permissions__=["memberaudit.basic_access"],
            main_character__character=EveCharacterFactory(
                corporation__alliance=alliance
            ),
        )
        cls.user_other = UserMainFactory(permissions__=["memberaudit.basic_access"])
        UserMainFactory()  # user with no access
        cls.eve_character = EveCharacterFactory(corporation=cls.corporation)

    def test_should_see_own_user_only(self):
        # given
        user = UserMainFactory(
            permissions__=["memberaudit.basic_access"],
            main_character__character=self.eve_character,
        )
        # when
        got = General.accessible_users(user)
        # then
        self.assertCountEqual(got, [user])

    def test_should_see_any_memberaudit_users(self):
        # given
        user = UserMainFactory(
            permissions__=["memberaudit.basic_access", "memberaudit.view_everything"],
            main_character__character=self.eve_character,
        )
        # when
        got = General.accessible_users(user=user)
        # then
        self.assertCountEqual(
            got,
            [
                user,
                self.user_same_corporation,
                self.user_same_alliance,
                self.user_other,
            ],
        )

    def test_should_see_same_alliance_only(self):
        # given
        user = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_same_alliance",
            ],
            main_character__character=self.eve_character,
        )
        # when
        got = General.accessible_users(user=user)
        # then
        self.assertCountEqual(
            got,
            [
                user,
                self.user_same_corporation,
                self.user_same_alliance,
            ],
        )

    def test_should_see_same_corporation_only(self):
        # given
        user = UserMainFactory(
            permissions__=[
                "memberaudit.basic_access",
                "memberaudit.view_same_corporation",
            ],
            main_character__character=self.eve_character,
        )
        # when
        got = General.accessible_users(user=user)
        # then
        self.assertCountEqual(got, [user, self.user_same_corporation])


class TestLocation(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.location_solar_system = LocationSolarSystemFactory()
        cls.location_asset_safety = LocationAssetSafetyFactory()
        cls.location_station = LocationStationFactory()
        cls.location_structure = LocationStructureFactory()
        cls.location_empty = Location.objects.create(id=1_900_900_000_000)
        cls.location_unknown = LocationUnknownFactory()

    def test_str(self):
        self.assertEqual(str(self.location_structure), self.location_structure.name)

    def test_checks_with_solar_system(self):
        location = self.location_solar_system
        self.assertTrue(location.is_solar_system)
        self.assertFalse(location.is_station)
        self.assertFalse(location.is_structure)
        self.assertFalse(Location.is_asset_safety_id(location.id))
        self.assertFalse(location.is_empty)

    def test_checks_with_station(self):
        location = self.location_station
        self.assertFalse(location.is_solar_system)
        self.assertTrue(location.is_station)
        self.assertFalse(location.is_structure)
        self.assertFalse(Location.is_asset_safety_id(location.id))
        self.assertFalse(location.is_empty)

    def test_checks_with_structure(self):
        location = self.location_structure
        self.assertFalse(location.is_solar_system)
        self.assertFalse(location.is_station)
        self.assertTrue(location.is_structure)
        self.assertFalse(Location.is_asset_safety_id(location.id))
        self.assertFalse(location.is_empty)

    def test_checks_with_asset_safety(self):
        location = self.location_asset_safety
        self.assertFalse(location.is_solar_system)
        self.assertFalse(location.is_station)
        self.assertFalse(location.is_structure)
        self.assertTrue(Location.is_asset_safety_id(location.id))
        self.assertFalse(location.is_empty)

    def test_checks_with_empty_location(self):
        location = self.location_empty
        self.assertFalse(location.is_solar_system)
        self.assertFalse(location.is_station)
        self.assertTrue(location.is_structure)
        self.assertFalse(Location.is_asset_safety_id(location.id))
        self.assertTrue(location.is_empty)

    def test_solar_system_url(self):
        obj_1 = self.location_structure
        obj_2 = Location.objects.create(id=1_000_000_000_999)

        self.assertTrue(obj_1.solar_system_url)
        self.assertFalse(obj_2.solar_system_url)

    def test_name_plus(self):
        self.assertEqual(
            self.location_structure.name_plus, self.location_structure.name
        )
        self.assertEqual(self.location_station.name_plus, self.location_station.name)
        self.assertEqual(
            self.location_solar_system.name_plus, self.location_solar_system.name
        )
        self.assertEqual(self.location_asset_safety.name_plus, "ASSET SAFETY")
        self.assertIn("unknown", self.location_unknown.name_plus)

    def test_should_return_correct_asset_location_type(self):
        cases = [
            ("station", self.location_station, "station"),
            ("structure", self.location_structure, "item"),
            ("solar system", self.location_solar_system, "solar_system"),
            ("unknown placeholder", self.location_unknown, "solar_system"),
            ("empty_location", self.location_empty, "item"),
        ]
        for name, location, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(location.asset_location_type(), expected)


class TestComplianceGroupDesignation(NoSocketsTestCase):
    def test_should_ensure_new_compliance_groups_are_internal(self):
        # given
        group = GroupFactory(authgroup__internal=False)
        self.assertFalse(group.authgroup.internal)
        # when
        ComplianceGroupDesignation.objects.create(group=group)
        # then
        group.refresh_from_db()
        self.assertTrue(group.authgroup.internal)


class TestSkillSet_Clone(NoSocketsTestCase):
    def test_should_clone_a_skill_set(self):
        # given
        user = UserMainBasicAccessFactory()
        skill_set_1 = SkillSetFactory()
        skill_type = NavigationSkillTypeFactory()
        skill_1 = SkillSetSkillFactory(
            skill_set=skill_set_1,
            eve_type=skill_type,
            required_level=3,
            recommended_level=5,
        )
        # when
        skill_set_2 = skill_set_1.clone(user=user)
        # then
        self.assertNotEqual(skill_set_2.pk, skill_set_1.pk)
        self.assertEqual(skill_set_2.description, skill_set_1.description)
        self.assertEqual(skill_set_2.is_visible, skill_set_1.is_visible)
        self.assertNotEqual(skill_set_2.last_modified_at, skill_set_1.last_modified_at)
        self.assertEqual(skill_set_2.last_modified_by, user)
        self.assertEqual(skill_set_2.ship_type, skill_set_1.ship_type)

        skill_2: SkillSetSkill = skill_set_2.skills.first()
        self.assertNotEqual(skill_2.pk, skill_1.pk)
        self.assertEqual(skill_2.eve_type, skill_1.eve_type)
        self.assertEqual(skill_2.required_level, skill_1.required_level)
        self.assertEqual(skill_2.recommended_level, skill_1.recommended_level)


class TestSkillSet_IconUrl(NoSocketsTestCase):
    def test_should_return_default_icon_when_no_ship_type(self):
        # given
        ss = SkillSetFactory(ship_type=None)

        # when
        got = ss.icon_url(64)

        # then
        want = f"https://images.evetech.net/types/{SKILL_SET_DEFAULT_ICON_TYPE_ID}/icon?size=64"
        self.assertEqual(got, want)

    def test_should_return_ship_type_icon_when_defined(self):
        # given
        et = EveTypeFactory()
        ss = SkillSetFactory(ship_type=et)

        # when
        got = ss.icon_url(64)

        # then
        want = f"https://images.evetech.net/types/{et.id}/icon?size=64"
        self.assertEqual(got, want)


class TestPermissions(NoSocketsTestCase):
    def test_should_have_default_permissions_for_skill_set_models(self):
        for model_class in [
            EveSkillType,
            EveShipType,
            SkillSet,
            SkillSetGroup,
            SkillSetSkill,
        ]:
            with self.subTest(model=model_class.__name__):
                # when/then
                self.assertTrue(permissions_for_model(model_class).exists())


class TestSkillSetSkill(NoSocketsTestCase):
    def test_should_return_str(self):
        # given
        obj = SkillSetSkillFactory()
        # when/then
        self.assertIn(obj.eve_type.name, str(obj))

    def test_should_return_str_when_required_skill(self):
        # given
        obj = SkillSetSkillFactory(required_level=1)
        # when/then
        self.assertIn(obj.eve_type.name, obj.required_skill_str)

    def test_should_return_empty_string_when_not_required_skill(self):
        # given
        obj = SkillSetSkillFactory(required_level=None)
        # when/then
        self.assertEqual(obj.required_skill_str, "")

    def test_should_return_str_when_recommended_skill(self):
        # given
        obj = SkillSetSkillFactory(recommended_level=1)
        # when/then
        self.assertIn(obj.eve_type.name, obj.recommended_skill_str)

    def test_should_return_empty_string_when_not_recommended_skill(self):
        # given
        obj = SkillSetSkillFactory(recommended_level=None)
        # when/then
        self.assertEqual(obj.recommended_skill_str, "")

    def test_should_return_true_when_skill_is_required(self):
        # given
        obj = SkillSetSkillFactory(required_level=1)
        # when/then
        self.assertTrue(obj.is_required)

    def test_should_return_false_when_skill_is_not_required(self):
        # given
        obj = SkillSetSkillFactory(required_level=None)
        # when/then
        self.assertFalse(obj.is_required)

    def test_should_return_maximum_skill_str(self):
        # given
        obj = SkillSetSkillFactory(recommended_level=1)
        # when/then
        self.assertIn(obj.eve_type.name, obj.maximum_skill_str)
