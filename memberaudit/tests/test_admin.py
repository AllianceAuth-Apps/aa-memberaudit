from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils.timezone import now

from allianceauth.eveonline.models import EveCorporationInfo
from app_utils.testdata_factories import UserFactory
from app_utils.testing import (
    create_authgroup,
    create_state,
    create_user_from_evecharacter,
)

from memberaudit.admin import (
    CharacterAdmin,
    ComplianceGroupDesignationAdmin,
    ComplianceGroupDesignationForm,
    SkillSetAdmin,
    SkillSetGroupAdmin,
)
from memberaudit.models import (
    Character,
    ComplianceGroupDesignation,
    SkillSet,
    SkillSetGroup,
)

from .testdata.factories import (
    create_character_update_status,
    create_compliance_group,
    create_skill_set,
)
from .testdata.load_entities import load_entities
from .testdata.load_eveuniverse import load_eveuniverse
from .utils import (
    add_memberaudit_character_to_user,
    create_memberaudit_character,
    create_user_from_evecharacter_with_access,
)

ADMIN_PATH = "memberaudit.admin"


class MockRequest(object):
    def __init__(self, user=None, post=None):
        self.user = user
        self.POST = post

    def get_full_path(self):
        return "/dummy-full-path"


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestComplianceGroupDesignationAdmin(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.modeladmin = ComplianceGroupDesignationAdmin(
            model=ComplianceGroupDesignation, admin_site=AdminSite()
        )
        load_entities()
        cls.user = UserFactory(is_staff=True, is_superuser=True)

    def test_should_remove_deleted_compliance_group_from_users(self):
        # given
        compliance_group = create_compliance_group()
        obj = compliance_group.compliancegroupdesignation
        user_compliant, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        add_memberaudit_character_to_user(user_compliant, 1001)
        user_compliant.groups.add(compliance_group)
        request = MockRequest(user=user_compliant)
        queryset = ComplianceGroupDesignation.objects.filter(pk=obj.pk)
        # when
        self.modeladmin.delete_queryset(request, queryset)
        # then
        self.assertFalse(ComplianceGroupDesignation.objects.filter(pk=obj.pk).exists())
        self.assertNotIn(compliance_group, user_compliant.groups.all())

    def test_should_add_group_to_compliant_users_when_created(self):
        # given
        compliance_group = create_authgroup(internal=True)
        user_compliant, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        add_memberaudit_character_to_user(user_compliant, 1001)
        user_non_compliant, _ = create_user_from_evecharacter(
            1002, permissions=["memberaudit.basic_access"]
        )
        request = MockRequest(user=user_compliant)
        obj = ComplianceGroupDesignation(group=compliance_group)
        form = ComplianceGroupDesignationForm()
        # when
        self.modeladmin.save_model(request, obj, form, False)
        # then
        self.assertTrue(ComplianceGroupDesignation.objects.filter(pk=obj.pk).exists())
        self.assertIn(compliance_group, user_compliant.groups.all())
        self.assertNotIn(compliance_group, user_non_compliant.groups.all())

    def test_should_add_state_group_to_compliant_users_when_state_is_matching(self):
        # given
        member_corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        my_state = create_state(member_corporations=[member_corporation], priority=200)
        compliance_group = create_authgroup(internal=True, states=[my_state])
        user_compliant, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        add_memberaudit_character_to_user(user_compliant, 1001)
        request = MockRequest(user=user_compliant)
        obj = ComplianceGroupDesignation(group=compliance_group)
        form = ComplianceGroupDesignationForm()
        # when
        self.modeladmin.save_model(request, obj, form, False)
        # then
        self.assertTrue(ComplianceGroupDesignation.objects.filter(pk=obj.pk).exists())
        self.assertIn(compliance_group, user_compliant.groups.all())

    def test_should_not_add_new_state_group_to_compliant_user_when_state_not_matching(
        self,
    ):
        # given
        my_state = create_state(priority=200)
        compliance_group = create_authgroup(internal=True, states=[my_state])
        user_compliant, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        add_memberaudit_character_to_user(user_compliant, 1001)
        request = MockRequest(user=user_compliant)
        obj = ComplianceGroupDesignation(group=compliance_group)
        form = ComplianceGroupDesignationForm()
        # when
        self.modeladmin.save_model(request, obj, form, False)
        # then
        self.assertNotIn(compliance_group, user_compliant.groups.all())

    def test_should_return_group_name(self):
        # given
        compliance_group = create_compliance_group(name="alpha")
        obj = compliance_group.compliancegroupdesignation
        # when
        result = self.modeladmin._group_name(obj)
        # then
        self.assertEqual(result, "alpha")

    def test_should_return_states_when_defined(self):
        # given
        my_state = create_state(priority=200, name="bravo")
        compliance_group = create_compliance_group(states=[my_state])
        obj = compliance_group.compliancegroupdesignation
        # when
        result = self.modeladmin._states(obj)
        # then
        self.assertIn("bravo", result)

    def test_should_return_empty_when_no_state_defined(self):
        # given
        compliance_group = create_compliance_group()
        obj = compliance_group.compliancegroupdesignation
        # when
        result = self.modeladmin._states(obj)
        # then
        self.assertEqual(result, "-")


class TestCharacterAdmin(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.modeladmin = CharacterAdmin(model=Character, admin_site=AdminSite())
        load_eveuniverse()
        load_entities()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.eve_character.character_ownership.user

    def test_column_character(self):
        self.assertEqual(self.modeladmin._character(self.character), "Bruce Wayne")

    def test_column_main_normal(self):
        self.assertEqual(self.modeladmin._main(self.character), "Bruce Wayne")

    def test_column_main_no_main(self):
        # given
        character = create_memberaudit_character(1002)
        user = character.eve_character.character_ownership.user
        user.profile.main_character = None
        user.profile.save()
        # when
        self.assertIsNone(self.modeladmin._main(character))

    def test_column_state(self):
        self.assertEqual(self.modeladmin._state(self.character), "Guest")

    def test_column_organization_normal(self):
        self.assertEqual(
            self.modeladmin._organization(self.character), "Wayne Technologies [WYN]"
        )

    def test_column_organization_no_main(self):
        # given
        character = create_memberaudit_character(1002)
        user = character.eve_character.character_ownership.user
        user.profile.main_character = None
        user.profile.save()
        # when
        self.assertIsNone(self.modeladmin._organization(character))

    def test_column_missing_sections_none(self):
        # given
        for section in Character.UpdateSection:
            create_character_update_status(character=self.character, section=section)
        self.assertIsNone(self.modeladmin._missing_sections(self.character))

    def test_column_missing_sections_two_missing(self):
        # given
        sections = [
            obj
            for obj in Character.UpdateSection
            if obj is not Character.UpdateSection.ASSETS
            and obj is not Character.UpdateSection.CONTRACTS
        ]
        for section in sections:
            create_character_update_status(character=self.character, section=section)
        self.assertListEqual(
            self.modeladmin._missing_sections(self.character), ["assets", "contracts"]
        )

    @patch(ADMIN_PATH + ".CharacterAdmin.message_user")
    @patch(ADMIN_PATH + ".tasks.update_character")
    def test_should_update_characters(
        self, mock_task_update_character, mock_message_user
    ):
        # given
        request = MockRequest(user=self.user)
        queryset = Character.objects.all()
        # when
        self.modeladmin.update_characters(request, queryset)
        # then
        self.assertEqual(mock_task_update_character.apply_async.call_count, 1)
        self.assertTrue(mock_message_user.called)


@patch(ADMIN_PATH + ".CharacterAdmin.message_user")
@patch(ADMIN_PATH + ".tasks.delete_objects")
class TestCharacterDeleteCharactersAdmin(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.modeladmin = CharacterAdmin(model=Character, admin_site=AdminSite())
        load_eveuniverse()
        load_entities()
        cls.user = UserFactory(is_staff=True, is_superuser=True)

    def test_should_delete_characters_1(
        self, mock_task_delete_characters, mock_message_user
    ):
        # given
        factory = RequestFactory()
        request = factory.get(reverse("admin:memberaudit_character_changelist"))
        create_memberaudit_character(1001)
        queryset = Character.objects.all()
        # when
        response = self.modeladmin.delete_objects(request, queryset)
        # then
        self.assertEqual(response.status_code, 200)

    def test_should_delete_characters_2(
        self, mock_task_delete_characters, mock_message_user
    ):
        # given
        request = MockRequest(user=self.user, post="apply")
        create_memberaudit_character(1001)
        queryset = Character.objects.all()
        # when
        self.modeladmin.delete_objects(request, queryset)
        # then
        self.assertEqual(mock_task_delete_characters.apply_async.call_count, 1)
        self.assertTrue(mock_message_user.called)


@patch(ADMIN_PATH + ".tasks.update_characters_skill_checks")
class TestSkillSetAdmin(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.modeladmin = SkillSetAdmin(model=SkillSet, admin_site=AdminSite())
        load_eveuniverse()
        load_entities()
        cls.user, _ = create_user_from_evecharacter_with_access(1001)

    def test_save_model(self, mock_update_characters_skill_checks):
        # given
        obj = SkillSet(name="Dummy")
        request = MockRequest(self.user)
        form = self.modeladmin.get_form(request)
        my_now = now()
        # when
        with patch(ADMIN_PATH + ".now", lambda: my_now):
            self.modeladmin.save_model(request, obj, form, True)
        # then
        obj_2: SkillSet = SkillSet.objects.get(name="Dummy")
        self.assertEqual(obj_2.last_modified_by, self.user)
        self.assertEqual(obj_2.last_modified_at, my_now)
        self.assertTrue(mock_update_characters_skill_checks.apply_async.called)

    def test_delete_model(self, mock_update_characters_skill_checks):
        # given
        obj = create_skill_set(name="Dummy")
        request = MockRequest(self.user)
        # when
        self.modeladmin.delete_model(request, obj)
        # then
        self.assertFalse(SkillSet.objects.filter(pk=obj.pk).exists())
        self.assertTrue(mock_update_characters_skill_checks.apply_async.called)

    # def test_ship_type_filter(self):
    #     class SkillSetAdminTest(SkillSetAdmin):
    #         list_filter = (SkillSetShipTypeFilter,)

    #     my_modeladmin = SkillSetAdminTest(SkillSet, AdminSite())

    #     ss_1 = SkillSet.objects.create(name="Set 1")
    #     ss_2 = SkillSet.objects.create(
    #         name="Set 2", ship_type=EveShipType.objects.get(id=603)
    #     )

    #     # Make sure the lookups are correct
    #     request = self.factory.get("/")
    #     request.user = self.user
    #     changelist = my_modeladmin.get_changelist_instance(request)
    #     filters = changelist.get_filters(request)
    #     filterspec = filters[0][0]
    #     expected = [("yes", "yes"), ("no", "no")]
    #     self.assertEqual(filterspec.lookup_choices, expected)

    #     # Make sure the correct queryset is returned
    #     request = self.factory.get("/", {"is_ship_type": "yes"})
    #     request.user = self.user
    #     changelist = my_modeladmin.get_changelist_instance(request)
    #     queryset = changelist.get_queryset(request)
    #     expected = {ss_2}
    #     self.assertSetEqual(set(queryset), expected)

    #     # Make sure the correct queryset is returned
    #     request = self.factory.get("/", {"is_ship_type": "no"})
    #     request.user = self.user
    #     changelist = my_modeladmin.get_changelist_instance(request)
    #     queryset = changelist.get_queryset(request)
    #     expected = {ss_1}
    #     self.assertSetEqual(set(queryset), expected)


class TestSkillSetSkillAdmin(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        cls.user = UserFactory(is_staff=True, is_superuser=True)

    def test_should_create_new_skill_set_with_required_level_only(self):
        # given
        self.client.force_login(self.user)
        # when
        response = self.client.post(
            "/admin/memberaudit/skillset/add/",
            data={
                "name": "Bla Bla",
                "skills-TOTAL_FORMS": 1,
                "skills-INITIAL_FORMS": 0,
                "skills-MIN_NUM_FORMS": 1,
                "skills-MAX_NUM_FORMS": 1000,
                "skills-0-eve_type": 24311,
                "skills-0-required_level": 1,
            },
        )
        # then
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SkillSet.objects.filter(name="Bla Bla").count(), 1)

    def test_should_create_new_skill_set_with_recommended_level_only(self):
        # given
        self.client.force_login(self.user)
        # when
        response = self.client.post(
            "/admin/memberaudit/skillset/add/",
            data={
                "name": "Bla Bla",
                "skills-TOTAL_FORMS": 1,
                "skills-INITIAL_FORMS": 0,
                "skills-MIN_NUM_FORMS": 1,
                "skills-MAX_NUM_FORMS": 1000,
                "skills-0-eve_type": 24311,
                "skills-0-recommended_level": 1,
            },
        )
        # then
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SkillSet.objects.filter(name="Bla Bla").count(), 1)

    def test_should_raise_error_when_no_level_given(self):
        # given
        self.client.force_login(self.user)
        # when
        response = self.client.post(
            "/admin/memberaudit/skillset/add/",
            data={
                "name": "Bla Bla",
                "skills-TOTAL_FORMS": 1,
                "skills-INITIAL_FORMS": 0,
                "skills-MIN_NUM_FORMS": 1,
                "skills-MAX_NUM_FORMS": 1000,
                "skills-0-eve_type": 24311,
            },
        )
        # then
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.content.decode("utf-8"))


class TestSkillSetGroupAdmin(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        cls.modeladmin = SkillSetGroupAdmin(model=SkillSetGroup, admin_site=AdminSite())
        load_eveuniverse()
        load_entities()
        cls.user = UserFactory(is_staff=True, is_superuser=True)

    def test_save_model(self):
        # given
        obj = SkillSetGroup(name="Dummy")
        request = MockRequest(self.user)
        form = self.modeladmin.get_form(request)
        my_now = now()
        # when
        with patch(ADMIN_PATH + ".now", lambda: my_now):
            self.modeladmin.save_model(request, obj, form, True)
        # then
        obj_2: SkillSetGroup = SkillSetGroup.objects.get(name="Dummy")
        self.assertEqual(obj_2.last_modified_by, self.user)
        self.assertEqual(obj_2.last_modified_at, my_now)


class TestCharacterAdminUi(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        cls.user = UserFactory(is_staff=True, is_superuser=True)
        load_entities()
        cls.character = create_memberaudit_character(1001)

    def test_should_render_list_view(self):
        # given
        self.client.force_login(self.user)
        # when
        response = self.client.get("/admin/memberaudit/character/")
        # then
        self.assertEqual(response.status_code, 200)
        self.assertIn("Bruce Wayne", response.content.decode("utf-8"))

    def test_should_render_change_view(self):
        # given
        self.client.force_login(self.user)
        # when
        response = self.client.get(
            f"/admin/memberaudit/character/{self.character.pk}/change/"
        )
        # then
        self.assertEqual(response.status_code, 200)
        self.assertIn("Bruce Wayne", response.content.decode("utf-8"))
