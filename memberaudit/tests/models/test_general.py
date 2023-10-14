from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from eveuniverse.models import EveSolarSystem, EveType

from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testing import (
    NoSocketsTestCase,
    create_authgroup,
    create_user_from_evecharacter,
    queryset_pks,
)

from memberaudit.models import (
    EveShipType,
    EveSkillType,
    General,
    Location,
    MailEntity,
    SkillSet,
    SkillSetGroup,
    SkillSetSkill,
)

from ..testdata.factories import (
    create_compliance_group_designation,
    create_skill_set,
    create_skill_set_skill,
)
from ..testdata.load_entities import load_entities
from ..testdata.load_eveuniverse import load_eveuniverse
from ..testdata.load_locations import load_locations
from ..utils import (
    add_auth_character_to_user,
    add_memberaudit_character_to_user,
    create_memberaudit_character,
    permissions_for_model,
)

MODELS_PATH = "memberaudit.models"
MANAGERS_PATH = "memberaudit.managers"
TASKS_PATH = "memberaudit.tasks"


class TestMailEntity(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_entities()

    def test_str(self):
        obj, _ = MailEntity.objects.update_or_create_from_eve_entity_id(1001)
        self.assertEqual(str(obj), "Bruce Wayne")

    def test_repr(self):
        obj, _ = MailEntity.objects.update_or_create_from_eve_entity_id(1001)
        self.assertEqual(
            repr(obj), "MailEntity(id=1001, category=CH, name='Bruce Wayne')"
        )

    def test_eve_entity_categories(self):
        obj, _ = MailEntity.objects.update_or_create_from_eve_entity_id(1001)
        self.assertSetEqual(
            obj.eve_entity_categories,
            {
                MailEntity.Category.ALLIANCE,
                MailEntity.Category.CHARACTER,
                MailEntity.Category.CORPORATION,
            },
        )

    def test_name_plus_1(self):
        obj, _ = MailEntity.objects.update_or_create_from_eve_entity_id(1001)
        self.assertEqual(obj.name_plus, "Bruce Wayne")

    def test_name_plus_2(self):
        obj = MailEntity.objects.create(id=42, category=MailEntity.Category.ALLIANCE)
        self.assertEqual(obj.name_plus, "Alliance #42")

    def test_need_to_specify_category(self):
        with self.assertRaises(ValidationError):
            MailEntity.objects.create(id=1)

    def test_url_1(self):
        obj, _ = MailEntity.objects.update_or_create_from_eve_entity_id(3001)
        self.assertIn("dotlan", obj.external_url())

    def test_url_2(self):
        obj, _ = MailEntity.objects.update_or_create_from_eve_entity_id(2001)
        self.assertIn("dotlan", obj.external_url())

    def test_url_3(self):
        obj, _ = MailEntity.objects.update_or_create_from_eve_entity_id(1001)
        self.assertIn("evewho", obj.external_url())

    def test_url_4(self):
        obj = MailEntity.objects.create(
            id=42, category=MailEntity.Category.MAILING_LIST, name="Dummy"
        )
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
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_entities()

    def test_should_return_compliant_users_only(self):
        # given
        # compliant user both chars registered
        user_compliant, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        add_memberaudit_character_to_user(user_compliant, 1001)
        add_memberaudit_character_to_user(user_compliant, 1101)
        # non-compliant user one char not registered
        user_non_compliant_1, _ = create_user_from_evecharacter(
            1002, permissions=["memberaudit.basic_access"]
        )
        add_memberaudit_character_to_user(user_compliant, 1002)
        add_auth_character_to_user(user_non_compliant_1, 1102)
        # non-compliant user with char registered, but missing permission
        user_non_compliant_2, _ = create_user_from_evecharacter(1003)
        add_memberaudit_character_to_user(user_non_compliant_2, 1003)
        # when
        result = General.compliant_users()
        # then
        self.assertQuerysetEqual(result, User.objects.filter(pk=user_compliant.pk))

    def test_should_add_group_to_compliant_users(self):
        # given
        group = create_authgroup(internal=True)
        user_compliant, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        add_memberaudit_character_to_user(user_compliant, 1001)
        user_non_compliant, _ = create_user_from_evecharacter(
            1002, permissions=["memberaudit.basic_access"]
        )
        # when
        General.add_compliant_users_to_group(group)
        # then
        self.assertIn(group, user_compliant.groups.all())
        self.assertNotIn(group, user_non_compliant.groups.all())


class TestGeneralUserHasAccess(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        character_1002 = create_memberaudit_character(1002)
        cls.user_1002 = character_1002.eve_character.character_ownership.user
        character_1003 = create_memberaudit_character(1003)
        cls.user_1003 = character_1003.eve_character.character_ownership.user
        character_1101 = create_memberaudit_character(1101)
        cls.user_1101 = character_1101.eve_character.character_ownership.user
        cls.user_dummy = AuthUtils.create_user("No-access-to-Member-Audit")

    def setUp(self) -> None:
        character_1001 = create_memberaudit_character(1001)
        self.user_1001 = character_1001.eve_character.character_ownership.user

    def test_should_see_own_user_only(self):
        # when
        result = General.accessible_users(user=self.user_1001)
        # then
        self.assertSetEqual(queryset_pks(result), {self.user_1001.pk})

    def test_should_see_all_memberaudit_users(self):
        # given
        self.user_1001 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_everything", self.user_1001
        )
        # when
        result = General.accessible_users(user=self.user_1001)
        # then
        self.assertSetEqual(
            queryset_pks(result),
            {
                self.user_1001.pk,
                self.user_1002.pk,
                self.user_1003.pk,
                self.user_1101.pk,
            },
        )

    def test_should_see_own_alliance_only(self):
        # given
        self.user_1001 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_alliance", self.user_1001
        )
        # when
        result = General.accessible_users(user=self.user_1001)
        # then
        self.assertSetEqual(
            queryset_pks(result),
            {self.user_1001.pk, self.user_1002.pk, self.user_1003.pk},
        )

    def test_should_see_own_corporation_only(self):
        # given
        self.user_1001 = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.view_same_corporation", self.user_1001
        )
        # when
        result = General.accessible_users(user=self.user_1001)
        # then
        self.assertSetEqual(
            queryset_pks(result), {self.user_1001.pk, self.user_1002.pk}
        )


class TestLocation(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()

    def test_str(self):
        location = Location.objects.get(id=1000000000001)
        self.assertEqual(str(location), "Amamake - Test Structure Alpha")

    def test_repr(self):
        location = Location.objects.get(id=1000000000001)
        self.assertEqual(
            repr(location),
            "Location(id=1000000000001, name='Amamake - Test Structure Alpha')",
        )

    def test_is_solar_system(self):
        location = Location.objects.create(
            id=30000142, eve_solar_system=EveSolarSystem.objects.get(id=30000142)
        )
        self.assertTrue(location.is_solar_system)
        self.assertFalse(location.is_station)
        self.assertFalse(location.is_structure)

    def test_is_station(self):
        location = Location.objects.get(id=60003760)
        self.assertFalse(location.is_solar_system)
        self.assertTrue(location.is_station)
        self.assertFalse(location.is_structure)

    def test_is_structure(self):
        location = Location.objects.get(id=1000000000001)
        self.assertFalse(location.is_solar_system)
        self.assertFalse(location.is_station)
        self.assertTrue(location.is_structure)

    def test_solar_system_url(self):
        obj_1 = Location.objects.get(id=1000000000001)
        obj_2 = Location.objects.create(id=1000000000999)

        self.assertIn("Amamake", obj_1.solar_system_url)
        self.assertEqual("", obj_2.solar_system_url)


class TestComplianceGroupDesignation(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_entities()

    def test_should_ensure_new_compliance_groups_are_internal(self):
        # given
        group = create_authgroup(internal=False)
        # when
        create_compliance_group_designation(group)
        # then
        group.refresh_from_db()
        self.assertTrue(group.authgroup.internal)


class TestSkillSet(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        cls.user = AuthUtils.create_user("Bruce Wayne")

    def test_should_clone_a_skill_set(self):
        # given
        obj_1 = create_skill_set()
        gunnery_skill = EveType.objects.get(name="Gunnery")
        skill_1 = create_skill_set_skill(
            obj_1, gunnery_skill, required_level=3, recommended_level=5
        )
        # when
        obj_2 = obj_1.clone(user=self.user)
        # then
        self.assertNotEqual(obj_2.pk, obj_1.pk)
        self.assertEqual(obj_2.description, obj_1.description)
        self.assertEqual(obj_2.is_visible, obj_1.is_visible)
        self.assertNotEqual(obj_2.last_modified_at, obj_1.last_modified_at)
        self.assertEqual(obj_2.last_modified_by, self.user)
        self.assertEqual(obj_2.ship_type, obj_1.ship_type)

        skill_2: SkillSetSkill = obj_2.skills.first()
        self.assertNotEqual(skill_2.pk, skill_1.pk)
        self.assertEqual(skill_2.eve_type, skill_1.eve_type)
        self.assertEqual(skill_2.required_level, skill_1.required_level)
        self.assertEqual(skill_2.recommended_level, skill_1.recommended_level)


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
