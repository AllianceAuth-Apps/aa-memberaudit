from unittest.mock import patch

from celery_once import AlreadyQueued

from django.core.cache import cache
from django.test import override_settings
from eveuniverse.models import EveEntity
from eveuniverse.tests.testdata.factories_2 import (
    EveEntityAllianceFactory,
    EveEntityCharacterFactory,
    EveEntityCorporationFactory,
)

from allianceauth.notifications.models import Notification
from app_utils.testdata_factories import (
    EveCharacterFactory,
    EveCorporationInfoFactory,
    UserMainFactory,
)
from app_utils.testing import NoSocketsTestCase, add_character_to_user

from memberaudit.models import ComplianceGroupDesignation, MailEntity
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    ComplianceGroupFactory,
    GroupFactory,
    MailEntityCharacterFactory,
    MailEntityMailingListFactory,
    MailEntityUnknownFactory,
    StateFactory,
    UserMainBasicAccessFactory,
)

MANAGERS_PATH = "memberaudit.managers.general"
TASKS_PATH = "memberaudit.tasks"


@patch(
    "allianceauth.authentication.models.notify", lambda *args, **kwargs: None
)  # state changes trigger notify
@patch(MANAGERS_PATH + ".notify", spec=True)
class TestComplianceGroupDesignation_UpdateUser(NoSocketsTestCase):
    def test_should_add_group_to_compliant_user_and_notify(self, mock_notify):
        # given
        compliance_group = ComplianceGroupFactory()
        other_group = GroupFactory(authgroup__internal=True)
        user = UserMainBasicAccessFactory()
        CharacterFactory(user=user)

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
        member_corporation = EveCorporationInfoFactory()
        my_state = StateFactory(member_corporations=[member_corporation], priority=200)
        compliance_group = ComplianceGroupFactory(authgroup__states=[my_state])
        ec = EveCharacterFactory(corporation=member_corporation)
        user = UserMainBasicAccessFactory(main_character__character=ec)
        CharacterFactory(user=user)

        # when
        ComplianceGroupDesignation.objects.update_user(user)

        # then
        self.assertIn(compliance_group, user.groups.all())

    def test_should_not_add_state_group_to_compliant_user_when_state_not_matches(
        self, mock_notify
    ):
        # given
        my_state = StateFactory(priority=200)
        compliance_group = ComplianceGroupFactory(authgroup__states=[my_state])
        user = UserMainBasicAccessFactory()
        CharacterFactory(user=user)

        # when
        ComplianceGroupDesignation.objects.update_user(user)

        # then
        self.assertNotIn(compliance_group, user.groups.all())
        self.assertFalse(user.notification_set.exists())

    # def test_should_not_notify_if_compliant_but_no_groups_added(self):
    #     # given
    #     member_corporation = EveCorporationInfo.objects.get(corporation_id=2001)
    #     my_state = create_state(member_corporations=[member_corporation], priority=200)
    #     compliance_group = ComplianceGroupFactory(states=[my_state])
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
        compliance_group_1 = ComplianceGroupFactory()
        compliance_group_2 = ComplianceGroupFactory()
        user = UserMainBasicAccessFactory()
        CharacterFactory(user=user)

        # when
        ComplianceGroupDesignation.objects.update_user(user)

        # then
        self.assertIn(compliance_group_1, user.groups.all())
        self.assertIn(compliance_group_2, user.groups.all())

    def test_should_remove_group_from_non_compliant_user_and_notify(self, mock_notify):
        # given
        compliance_group = ComplianceGroupFactory()
        other_group = GroupFactory(authgroup__internal=True)
        user = UserMainBasicAccessFactory()
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
        compliance_group_1 = ComplianceGroupFactory()
        compliance_group_2 = ComplianceGroupFactory()
        other_group = GroupFactory(authgroup__internal=True)
        user = UserMainBasicAccessFactory()
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
        compliance_group = ComplianceGroupFactory()
        user = UserMainBasicAccessFactory()
        CharacterFactory(user=user)
        add_character_to_user(user, EveCharacterFactory())
        user.groups.add(compliance_group)

        # when
        ComplianceGroupDesignation.objects.update_user(user)

        # then
        self.assertNotIn(compliance_group, user.groups.all())

    def test_user_without_basic_permission_is_not_compliant(self, mock_notify):
        # given
        compliance_group = ComplianceGroupFactory()
        user = UserMainFactory()
        CharacterFactory(user=user)
        user.groups.add(compliance_group)

        # when
        ComplianceGroupDesignation.objects.update_user(user)

        # then
        self.assertNotIn(compliance_group, user.groups.all())

    def test_should_add_missing_groups_if_user_remains_compliant(self, mock_notify):
        # given
        compliance_group_1 = ComplianceGroupFactory()
        compliance_group_2 = ComplianceGroupFactory()
        other_group = GroupFactory(authgroup__internal=True)
        user = UserMainBasicAccessFactory()
        CharacterFactory(user=user)
        user.groups.add(compliance_group_1)

        # when
        ComplianceGroupDesignation.objects.update_user(user)

        # then
        self.assertIn(compliance_group_1, user.groups.all())
        self.assertIn(compliance_group_2, user.groups.all())
        self.assertNotIn(other_group, user.groups.all())
        self.assertEqual(user.notification_set.count(), 0)


class TestMailEntityManager_GetOrCreateEsi(NoSocketsTestCase):
    def test_should_return_existing_items(self):
        # given
        obj_1 = MailEntityCharacterFactory()

        # when
        obj_2, created = MailEntity.objects.get_or_create_esi(id=obj_1.id)

        # then
        self.assertFalse(created)
        self.assertEqual(obj_2, obj_1)

    def test_should_create_from_existing_eve_entity_when_not_exists(self):
        # given
        eve_entity = EveEntityCharacterFactory()

        # when
        obj, created = MailEntity.objects.get_or_create_esi(id=eve_entity.id)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, eve_entity.name)


class TestMailEntityManager_UpdateOrCreateEsi(NoSocketsTestCase):
    def test_should_create_from_existing_eve_entity(self):
        # given
        eve_entity = EveEntityCharacterFactory()

        # given
        obj, created = MailEntity.objects.update_or_create_esi(id=eve_entity.id)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, eve_entity.name)

    def test_should_update_existing_mail_entity(self):
        # given
        obj_id = 42
        MailEntityUnknownFactory(id=obj_id)
        eve_entity = EveEntityCharacterFactory(id=obj_id)

        # when
        obj: MailEntity
        obj, created = MailEntity.objects.update_or_create_esi(id=obj_id)

        # then
        self.assertFalse(created)
        self.assertEqual(obj.name, eve_entity.name)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)

    def test_should_not_update_mailing_list(self):
        # given
        obj_1 = MailEntityMailingListFactory()

        # when
        obj_2: MailEntity
        obj_2, created = MailEntity.objects.update_or_create_esi(id=obj_1.id)

        # then
        self.assertFalse(created)
        self.assertEqual(obj_2.name, obj_1.name)
        # method must not create an EveEntity object for the mailing list
        self.assertFalse(EveEntity.objects.filter(id=obj_1.id).exists())

    def test_should_create_mailing_list(self):
        # given
        obj_1_id = 9001
        # when
        with patch(
            MANAGERS_PATH + ".EveEntity.objects.get_or_create_esi", spec=True
        ) as m:
            m.return_value = None, False
            obj_2: MailEntity
            obj_2, created = MailEntity.objects.update_or_create_esi(id=obj_1_id)

        # then
        self.assertTrue(created)
        self.assertEqual(obj_2.id, obj_1_id)
        self.assertEqual(obj_2.category, MailEntity.Category.MAILING_LIST)


class TestMailEntityManager_UpdateOrCreateFromEveEntity(NoSocketsTestCase):
    def test_should_create_from_eve_entity(self):
        # given
        eve_entity = EveEntityCharacterFactory()

        # when
        obj: MailEntity
        obj, created = MailEntity.objects.update_or_create_from_eve_entity(eve_entity)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, eve_entity.name)
        self.assertEqual(obj.id, eve_entity.id)

    def test_should_update_from_eve_entity(self):
        # given
        obj_1 = MailEntityUnknownFactory()
        eve_entity = EveEntityCharacterFactory(id=obj_1.id)

        # when
        obj_2: MailEntity
        obj_2, created = MailEntity.objects.update_or_create_from_eve_entity(eve_entity)

        # then
        self.assertFalse(created)
        self.assertEqual(obj_2.name, eve_entity.name)
        self.assertEqual(obj_2.category, MailEntity.Category.CHARACTER)


class TestMailEntityManager_BulkUpdateNames(NoSocketsTestCase):
    def test_can_bulk_resolve_from_existing_eve_entities(self):
        # given
        character = EveEntityCharacterFactory()
        corporation = EveEntityCorporationFactory()
        alliance = EveEntityAllianceFactory()
        obj_1 = MailEntityUnknownFactory(
            id=character.id, category=MailEntity.Category.CHARACTER
        )
        obj_2 = MailEntityUnknownFactory(
            id=corporation.id, category=MailEntity.Category.CORPORATION
        )
        obj_3 = MailEntityUnknownFactory(
            id=alliance.id, category=MailEntity.Category.ALLIANCE
        )

        # when
        MailEntity.objects.bulk_update_names([obj_1, obj_2, obj_3])

        # then
        obj_1.refresh_from_db()
        self.assertEqual(obj_1.name, character.name)
        obj_2.refresh_from_db()
        self.assertEqual(obj_2.name, corporation.name)
        obj_3.refresh_from_db()
        self.assertEqual(obj_3.name, alliance.name)

    def test_should_not_resolve_non_matching_categories(self):
        # given
        character = EveEntityCharacterFactory()
        obj_1 = MailEntityUnknownFactory(
            id=character.id, category=MailEntity.Category.CHARACTER
        )
        obj_2 = MailEntityUnknownFactory(
            id=9001, category=MailEntity.Category.MAILING_LIST
        )
        obj_3 = MailEntityUnknownFactory(id=9002, category=MailEntity.Category.UNKNOWN)

        # when
        MailEntity.objects.bulk_update_names([obj_1, obj_2, obj_3])

        # then
        self.assertEqual(obj_1.name, character.name)
        self.assertEqual(obj_2.name, "")
        self.assertEqual(obj_3.name, "")

    def test_should_do_nothing_when_list_is_empty(self):
        MailEntity.objects.bulk_update_names([])

    def test_should_overwrite_existing_names_for_matching_categories(self):
        # given
        character = EveEntityCharacterFactory()
        obj = MailEntityCharacterFactory(
            id=character.id, category=MailEntity.Category.CHARACTER, name="John Doe"
        )

        # when
        MailEntity.objects.bulk_update_names([obj])

        # then
        self.assertEqual(obj.name, character.name)

    def test_should_not_overwrite_existing_names_for_matching_categories_when_disabled(
        self,
    ):
        # given
        character = EveEntityCharacterFactory()
        obj = MailEntityCharacterFactory(
            id=character.id, category=MailEntity.Category.CHARACTER, name="John Doe"
        )

        # when
        MailEntity.objects.bulk_update_names([obj], keep_names=True)

        # then
        self.assertEqual(obj.name, "John Doe")


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestMailEntityManager_GetOrCreateMailEntityEsiAsync(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cache.clear()

    def test_should_return_obj_when_it_exists(self):
        # given
        MailEntityCharacterFactory(
            id=1234, category=MailEntity.Category.CHARACTER, name="John Doe"
        )

        # when
        obj, created = MailEntity.objects.get_or_create_esi_async(id=1234)

        # then
        self.assertFalse(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "John Doe")

    def test_should_create_obj_async_when_it_not_exists(self):
        # given
        EveEntityCharacterFactory(id=1001, name="Bruce Wayne")

        # when
        obj: MailEntity
        obj, created = MailEntity.objects.get_or_create_esi_async(id=1001)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.UNKNOWN)
        self.assertEqual(obj.name, "")

        obj.refresh_from_db()
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_should_create_obj_sync_when_it_not_exists_and_not_mailing_list(self):
        # given
        EveEntityCharacterFactory(id=1001, name="Bruce Wayne")

        # when
        obj: MailEntity
        obj, created = MailEntity.objects.get_or_create_esi_async(
            id=1001, category=MailEntity.Category.CHARACTER
        )

        # then
        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TestMailEntityManager_UpdateOrCreateEsiAsync(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cache.clear()

    def test_should_create_obj_async_when_it_not_exists(self):
        # given
        EveEntityCharacterFactory(id=1001, name="Bruce Wayne")

        # when
        obj: MailEntity
        obj, created = MailEntity.objects.update_or_create_esi_async(1001)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.UNKNOWN)
        self.assertEqual(obj.name, "")

        obj.refresh_from_db()
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_should_update_obj_sync_when_it_exists_and_not_mailing_list(self):
        # given
        EveEntityCharacterFactory(id=1001, name="Bruce Wayne")
        MailEntityCharacterFactory(
            id=1001, category=MailEntity.Category.CHARACTER, name="John Doe"
        )

        # when
        obj: MailEntity
        obj, created = MailEntity.objects.update_or_create_esi_async(1001)

        # then
        self.assertFalse(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")

    def test_should_not_do_anything_when_obj_exists_and_is_mailing_list(self):
        # given
        MailEntityCharacterFactory(
            id=9001, category=MailEntity.Category.MAILING_LIST, name="Dummy"
        )

        # when
        obj: MailEntity
        obj, created = MailEntity.objects.update_or_create_esi_async(9001)

        # then
        self.assertFalse(created)
        self.assertEqual(obj.category, MailEntity.Category.MAILING_LIST)
        self.assertEqual(obj.name, "Dummy")

    def test_should_create_obj_sync_when_it_not_exists_and_not_mailing_list(self):
        # given
        EveEntityCharacterFactory(id=1001, name="Bruce Wayne")

        # when
        obj: MailEntity
        obj, created = MailEntity.objects.update_or_create_esi_async(
            1001, MailEntity.Category.CHARACTER
        )

        # then
        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.CHARACTER)
        self.assertEqual(obj.name, "Bruce Wayne")


class TestMailEntityManager_UpdateOrCreateEsiAsync2(NoSocketsTestCase):
    @patch(TASKS_PATH + ".update_mail_entity_esi", spec=True)
    def test_should_create_new_object_and_try_to_resolve(
        self, mock_task_update_mail_entity_esi
    ):
        # given
        EveEntityCharacterFactory(id=1001, name="Bruce Wayne")

        # when
        obj: MailEntity
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
        EveEntityCharacterFactory(id=1001, name="Bruce Wayne")

        # when
        obj: MailEntity
        obj, created = MailEntity.objects.update_or_create_esi_async(1001)

        # then
        self.assertTrue(created)
        self.assertEqual(obj.category, MailEntity.Category.UNKNOWN)
        self.assertEqual(obj.name, "")
        self.assertTrue(mock_task_update_mail_entity_esi.apply_async.called)
