from unittest.mock import patch

from celery_once import AlreadyQueued

from django.test import TestCase, override_settings
from eveuniverse.models import EveEntity, EveType

from allianceauth.eveonline.models import EveCorporationInfo
from allianceauth.notifications.models import Notification
from app_utils.testing import (
    NoSocketsTestCase,
    create_authgroup,
    create_state,
    create_user_from_evecharacter,
)

from memberaudit.models import ComplianceGroupDesignation, MailEntity, SkillSet
from memberaudit.tests.testdata.factories import (
    create_compliance_group,
    create_fitting,
    create_mail_entity,
    create_skill,
    create_skill_plan,
    create_skill_set_group,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.utils import (
    add_auth_character_to_user,
    add_memberaudit_character_to_user,
)

MANAGERS_PATH = "memberaudit.managers.general"
TASKS_PATH = "memberaudit.tasks"


@patch(
    "allianceauth.authentication.models.notify", lambda *args, **kwargs: None
)  # state changes trigger notify
@patch(MANAGERS_PATH + ".notify", spec=True)
class TestComplianceGroupDesignation(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    def test_should_add_group_to_compliant_user_and_notify(self, mock_notify):
        # given
        compliance_group = create_compliance_group()
        other_group = create_authgroup(internal=True)
        user, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        add_memberaudit_character_to_user(user, 1001)
        # when
        ComplianceGroupDesignation.objects.update_user(user)
        # then
        self.assertIn(compliance_group, user.groups.all())
        self.assertNotIn(other_group, user.groups.all())
        self.assertEqual(mock_notify.call_count, 1)
        args, kwargs = mock_notify.call_args
        self.assertEqual(kwargs["level"], Notification.Level.SUCCESS)
        self.assertEqual(args[0], user)

    def test_should_add_state_group_to_compliant_user_when_state_matches(
        self, mock_notify
    ):
        # given
        member_corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        my_state = create_state(member_corporations=[member_corporation], priority=200)
        compliance_group = create_compliance_group(states=[my_state])

        user, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        add_memberaudit_character_to_user(user, 1001)
        # when
        ComplianceGroupDesignation.objects.update_user(user)
        # then
        self.assertIn(compliance_group, user.groups.all())

    def test_should_not_add_state_group_to_compliant_user_when_state_not_matches(
        self, mock_notify
    ):
        # given
        my_state = create_state(priority=200)
        compliance_group = create_compliance_group(states=[my_state])
        user, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        add_memberaudit_character_to_user(user, 1001)
        # when
        ComplianceGroupDesignation.objects.update_user(user)
        # then
        self.assertNotIn(compliance_group, user.groups.all())
        self.assertFalse(user.notification_set.exists())

    # def test_should_not_notify_if_compliant_but_no_groups_added(self):
    #     # given
    #     member_corporation = EveCorporationInfo.objects.get(corporation_id=2001)
    #     my_state = create_state(member_corporations=[member_corporation], priority=200)
    #     compliance_group = create_compliance_group(states=[my_state])
    #     user, _ = create_user_from_evecharacter(
    #         1001, permissions=["memberaudit.basic_access"]
    #     )
    #     add_memberaudit_character_to_user(user, 1001)
    #     # when
    #     ComplianceGroupDesignation.objects.update_user(user)
    #     # then
    #     self.assertIn(compliance_group, user.groups.all())

    def test_should_add_multiple_groups_to_compliant_user(self, mock_notify):
        # given
        compliance_group_1 = create_compliance_group()
        compliance_group_2 = create_compliance_group()
        user, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        add_memberaudit_character_to_user(user, 1001)
        # when
        ComplianceGroupDesignation.objects.update_user(user)
        # then
        self.assertIn(compliance_group_1, user.groups.all())
        self.assertIn(compliance_group_2, user.groups.all())

    def test_should_remove_group_from_non_compliant_user_and_notify(self, mock_notify):
        # given
        compliance_group = create_compliance_group()
        other_group = create_authgroup(internal=True)
        user, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        user.groups.add(compliance_group, other_group)
        # when
        ComplianceGroupDesignation.objects.update_user(user)
        # then
        self.assertNotIn(compliance_group, user.groups.all())
        self.assertIn(other_group, user.groups.all())
        args, kwargs = mock_notify.call_args
        self.assertEqual(kwargs["level"], Notification.Level.WARNING)
        self.assertEqual(args[0], user)

    def test_should_remove_multiple_groups_from_non_compliant_user(self, mock_notify):
        # given
        compliance_group_1 = create_compliance_group()
        compliance_group_2 = create_compliance_group()
        other_group = create_authgroup(internal=True)
        user, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        user.groups.add(compliance_group_1, compliance_group_2, other_group)
        # when
        ComplianceGroupDesignation.objects.update_user(user)
        # then
        self.assertNotIn(compliance_group_1, user.groups.all())
        self.assertNotIn(compliance_group_2, user.groups.all())
        self.assertIn(other_group, user.groups.all())

    def test_user_with_one_registered_and_one_unregistered_character_is_not_compliant(
        self, mock_notify
    ):
        # given
        compliance_group = create_compliance_group()
        user, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        add_memberaudit_character_to_user(user, 1001)
        add_auth_character_to_user(user, 1002)
        user.groups.add(compliance_group)
        # when
        ComplianceGroupDesignation.objects.update_user(user)
        # then
        self.assertNotIn(compliance_group, user.groups.all())

    def test_user_without_basic_permission_is_not_compliant(self, mock_notify):
        # given
        compliance_group = create_compliance_group()
        user, _ = create_user_from_evecharacter(1001)
        add_memberaudit_character_to_user(user, 1001)
        user.groups.add(compliance_group)
        # when
        ComplianceGroupDesignation.objects.update_user(user)
        # then
        self.assertNotIn(compliance_group, user.groups.all())

    def test_should_add_missing_groups_if_user_remains_compliant(self, mock_notify):
        # given
        compliance_group_1 = create_compliance_group()
        compliance_group_2 = create_compliance_group()
        other_group = create_authgroup(internal=True)
        user, _ = create_user_from_evecharacter(
            1001, permissions=["memberaudit.basic_access"]
        )
        add_memberaudit_character_to_user(user, 1001)
        user.groups.add(compliance_group_1)
        # when
        ComplianceGroupDesignation.objects.update_user(user)
        # then
        self.assertIn(compliance_group_1, user.groups.all())
        self.assertIn(compliance_group_2, user.groups.all())
        self.assertNotIn(other_group, user.groups.all())
        self.assertEqual(user.notification_set.count(), 0)


class TestMailEntityManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    def test_get_or_create_esi_1(self):
        """When entity already exists, return it"""
        # given
        create_mail_entity(
            id=1234, category=MailEntity.Category.CHARACTER, name="John Doe"
        )
        # when
        obj, created = MailEntity.objects.get_or_create_esi(id=1234)
        # then
        self.assertFalse(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "John Doe")

    def test_get_or_create_esi_2(self):
        """When entity does not exist, create it from ESI / existing EveEntity"""
        obj, created = MailEntity.objects.get_or_create_esi(id=1001)

        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_update_or_create_esi_1(self):
        """When entity does not exist, create it from ESI / existing EveEntity"""
        obj, created = MailEntity.objects.update_or_create_esi(id=1001)

        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_update_or_create_esi_2(self):
        """When entity already exist and is not a mailing list,
        then update it from ESI / existing EveEntity
        """
        create_mail_entity(
            id=1001, category=MailEntity.Category.CHARACTER, name="John Doe"
        )
        obj, created = MailEntity.objects.update_or_create_esi(id=1001)

        self.assertFalse(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_update_or_create_esi_3(self):
        """When entity already exist and is a mailing list, then do nothing"""
        create_mail_entity(
            id=9001, category=MailEntity.Category.MAILING_LIST, name="Dummy"
        )
        obj, created = MailEntity.objects.update_or_create_esi(id=9001)

        self.assertFalse(created)
        self.assertEqual(obj.category, MailEntity.Category.MAILING_LIST)
        self.assertEqual(obj.name, "Dummy")
        # method must not create an EveEntity object for the mailing list
        self.assertFalse(EveEntity.objects.filter(id=9001).exists())

    def test_update_or_create_esi_4(self):
        """When entity does not exist and is a mailing list, then create it."""
        # when
        with patch(
            MANAGERS_PATH + ".EveEntity.objects.get_or_create_esi", spec=True
        ) as m:
            m.return_value = None, False
            obj, created = MailEntity.objects.update_or_create_esi(id=9001)
        # when
        self.assertTrue(created)
        self.assertEqual(obj.id, 9001)
        self.assertEqual(obj.category, MailEntity.Category.MAILING_LIST)

    def test_update_or_create_from_eve_entity_1(self):
        """When entity does not exist, create it from given EveEntity"""
        eve_entity = EveEntity.objects.get(id=1001)
        obj, created = MailEntity.objects.update_or_create_from_eve_entity(eve_entity)

        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_update_or_create_from_eve_entity_2(self):
        """When entity already exist, update it from given EveEntity"""
        create_mail_entity(
            id=1001, category=MailEntity.Category.CHARACTER, name="John Doe"
        )

        eve_entity = EveEntity.objects.get(id=1001)
        obj, created = MailEntity.objects.update_or_create_from_eve_entity(eve_entity)

        self.assertFalse(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_update_or_create_from_eve_entity_id_1(self):
        """When entity does not exist, create it from given EveEntity"""
        eve_entity = EveEntity.objects.get(id=1001)
        obj, created = MailEntity.objects.update_or_create_from_eve_entity_id(
            eve_entity.id
        )

        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_update_or_create_from_eve_entity_id_2(self):
        """When entity already exist, update it from given EveEntity"""
        create_mail_entity(
            id=1001, category=MailEntity.Category.CHARACTER, name="John Doe"
        )

        eve_entity = EveEntity.objects.get(id=1001)
        obj, created = MailEntity.objects.update_or_create_from_eve_entity_id(
            eve_entity.id
        )

        self.assertFalse(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_bulk_resolve_1(self):
        """Can resolve all 3 categories known by EveEntity"""
        obj_1001 = create_mail_entity(id=1001, category=MailEntity.Category.CHARACTER)
        obj_2001 = create_mail_entity(id=2001, category=MailEntity.Category.CORPORATION)
        obj_3001 = create_mail_entity(id=3001, category=MailEntity.Category.ALLIANCE)

        MailEntity.objects.bulk_update_names([obj_1001, obj_2001, obj_3001])

        self.assertEqual(obj_1001.name, "Bruce Wayne")
        self.assertEqual(obj_2001.name, "Wayne Technologies")
        self.assertEqual(obj_3001.name, "Wayne Enterprises")

    def test_bulk_resolve_2(self):
        """Will ignore categories not known to EveEntity"""

        obj_1001 = create_mail_entity(id=1001, category=MailEntity.Category.CHARACTER)
        obj_9001 = create_mail_entity(
            id=9001, category=MailEntity.Category.MAILING_LIST
        )
        obj_9002 = create_mail_entity(id=9002, category=MailEntity.Category.UNKNOWN)

        MailEntity.objects.bulk_update_names([obj_1001, obj_9001, obj_9002])

        self.assertEqual(obj_1001.name, "Bruce Wayne")
        self.assertEqual(obj_9001.name, "")
        self.assertEqual(obj_9002.name, "")

    def test_bulk_resolve_3(self):
        """When object list is empty, then no op"""

        try:
            MailEntity.objects.bulk_update_names([])
        except Exception as ex:
            self.fail(f"Unexpected exception: {ex}")

    def test_bulk_resolve_4(self):
        """When object already has a name, then update it"""
        obj_1001 = create_mail_entity(
            id=1001, category=MailEntity.Category.CHARACTER, name="John Doe"
        )

        MailEntity.objects.bulk_update_names([obj_1001])

        self.assertEqual(obj_1001.name, "Bruce Wayne")

    def test_bulk_resolve_5(self):
        """When object already has a name and respective option is chosen
        then ignore it
        """
        obj_1001 = create_mail_entity(
            id=1001, category=MailEntity.Category.CHARACTER, name="John Doe"
        )

        MailEntity.objects.bulk_update_names([obj_1001], keep_names=True)

        self.assertEqual(obj_1001.name, "John Doe")


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestMailEntityManagerAsync(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    def test_get_or_create_esi_async_1(self):
        """When entity already exists, return it"""

        create_mail_entity(
            id=1234, category=MailEntity.Category.CHARACTER, name="John Doe"
        )

        obj, created = MailEntity.objects.get_or_create_esi_async(id=1234)

        self.assertFalse(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "John Doe")

    def test_get_or_create_esi_async_2(self):
        """When entity does not exist and no category specified,
        then create it asynchronously from ESI / existing EveEntity
        """
        obj, created = MailEntity.objects.get_or_create_esi_async(id=1001)

        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.UNKNOWN)
        self.assertEqual(obj.name, "")

        obj.refresh_from_db()
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_get_or_create_esi_async_3(self):
        """When entity does not exist and category is not mailing list,
        then create it synchronously from ESI / existing EveEntity
        """
        obj, created = MailEntity.objects.get_or_create_esi_async(
            id=1001, category=MailEntity.Category.CHARACTER
        )

        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_update_or_create_esi_async_1(self):
        """When entity does not exist, create empty object and run task to resolve"""

        obj, created = MailEntity.objects.update_or_create_esi_async(1001)

        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.UNKNOWN)
        self.assertEqual(obj.name, "")

        obj.refresh_from_db()
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_update_or_create_esi_async_2(self):
        """When entity exists and not a mailing list, then update synchronously"""
        create_mail_entity(
            id=1001, category=MailEntity.Category.CHARACTER, name="John Doe"
        )

        obj, created = MailEntity.objects.update_or_create_esi_async(1001)

        self.assertFalse(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_update_or_create_esi_async_3(self):
        """When entity exists and is a mailing list, then do nothing"""
        create_mail_entity(
            id=9001, category=MailEntity.Category.MAILING_LIST, name="Dummy"
        )

        obj, created = MailEntity.objects.update_or_create_esi_async(9001)

        self.assertFalse(created)
        self.assertEqual(obj.category, MailEntity.Category.MAILING_LIST)
        self.assertEqual(obj.name, "Dummy")

    def test_update_or_create_esi_async_4(self):
        """When entity does not exist and category is not a mailing list,
        then create empty object from ESI synchronously
        """
        obj, created = MailEntity.objects.update_or_create_esi_async(
            1001, MailEntity.Category.CHARACTER
        )

        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")


class TestMailEntityManagerAsync2(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities()

    @patch(TASKS_PATH + ".update_mail_entity_esi", spec=True)
    def test_should_create_new_object_and_try_to_resolve(
        self, mock_task_update_mail_entity_esi
    ):
        # when
        obj, created = MailEntity.objects.update_or_create_esi_async(1001)
        # then
        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.UNKNOWN)
        self.assertEqual(obj.name, "")
        self.assertTrue(mock_task_update_mail_entity_esi.apply_async.called)

    @patch("memberaudit.tasks.update_mail_entity_esi", spec=True)
    def test_should_create_new_object_and_try_to_resolve_and_ignore_already_queued(
        self, mock_task_update_mail_entity_esi
    ):
        # given
        mock_task_update_mail_entity_esi.apply_async.side_effect = AlreadyQueued(10)
        # when
        obj, created = MailEntity.objects.update_or_create_esi_async(1001)
        # then
        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.UNKNOWN)
        self.assertEqual(obj.name, "")
        self.assertTrue(mock_task_update_mail_entity_esi.apply_async.called)


class TestSkillSetManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        cls.fitting = create_fitting(name="My fitting")

    def test_should_create_new_skill_set_from_fitting(self):
        # when
        skill_set, created = SkillSet.objects.update_or_create_from_fitting(
            fitting=self.fitting
        )
        # then
        self.assertTrue(created)
        self.assertEqual(skill_set.name, "My fitting")
        self.assertEqual(skill_set.ship_type.name, "Tristan")
        skills_str = {skill.required_skill_str for skill in skill_set.skills.all()}
        self.assertSetEqual(
            skills_str,
            {
                "Small Autocannon Specialization I",
                "Gunnery II",
                "Weapon Upgrades IV",
                "Light Drone Operation V",
                "Small Projectile Turret V",
                "Gallente Frigate I",
                "Propulsion Jamming II",
                "Drones V",
                "Amarr Drone Specialization I",
            },
        )

    def test_should_create_new_skill_set_from_fitting_and_assign_to_group(self):
        # given
        skill_set_group = create_skill_set_group()
        # when
        skill_set, created = SkillSet.objects.update_or_create_from_fitting(
            fitting=self.fitting, skill_set_group=skill_set_group
        )
        # then
        self.assertTrue(created)
        self.assertIn(skill_set, skill_set_group.skill_sets.all())

    def test_should_create_new_skill_set_from_skill_plan(self):
        # given
        skills = [
            create_skill(
                eve_type=EveType.objects.get(name="Small Autocannon Specialization"),
                level=1,
            ),
            create_skill(
                eve_type=EveType.objects.get(name="Light Drone Operation"),
                level=5,
            ),
        ]
        skill_plan = create_skill_plan(name="My skill plan", skills=skills)
        # when
        skill_set, created = SkillSet.objects.update_or_create_from_skill_plan(
            skill_plan=skill_plan
        )
        # then
        self.assertTrue(created)
        self.assertEqual(skill_set.name, "My skill plan")
        skills_str = {skill.required_skill_str for skill in skill_set.skills.all()}
        self.assertSetEqual(
            skills_str,
            {"Small Autocannon Specialization I", "Light Drone Operation V"},
        )

    def test_should_create_new_skill_set_from_skill_plan_and_assign_to_group(self):
        # given
        # given
        skills = [
            create_skill(
                eve_type=EveType.objects.get(name="Small Autocannon Specialization"),
                level=1,
            ),
            create_skill(
                eve_type=EveType.objects.get(name="Light Drone Operation"),
                level=5,
            ),
        ]
        skill_plan = create_skill_plan(name="My skill plan", skills=skills)
        skill_set_group = create_skill_set_group()
        # when
        skill_set, created = SkillSet.objects.update_or_create_from_skill_plan(
            skill_plan=skill_plan, skill_set_group=skill_set_group
        )
        # then
        self.assertTrue(created)
        self.assertIn(skill_set, skill_set_group.skill_sets.all())
