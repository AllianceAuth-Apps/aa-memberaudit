from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django_webtest import WebTest
from eveuniverse.models import EveEntity, EveType

from allianceauth.tests.auth_utils import AuthUtils
from app_utils.esi import EsiStatus
from app_utils.testdata_factories import UserFactory
from app_utils.testing import NoSocketsTestCase

from memberaudit import tasks
from memberaudit.models import (
    Character,
    CharacterContract,
    Location,
    MailEntity,
    SkillSet,
)

from .testdata.esi_client_stub import esi_client_stub, esi_stub
from .testdata.factories import (
    create_character_asset,
    create_character_contract,
    create_character_contract_item,
    create_character_mail,
    create_character_mail_label,
    create_mailing_list,
    create_skill_set,
)
from .testdata.load_entities import load_entities
from .testdata.load_eveuniverse import load_eveuniverse
from .testdata.load_locations import load_locations
from .utils import (
    add_auth_character_to_user,
    add_memberaudit_character_to_user,
    create_memberaudit_character,
    create_user_from_evecharacter_with_access,
    reset_celery_once_locks,
)

MANAGERS_PATH = "memberaudit.managers"
MODELS_PATH = "memberaudit.models"
TASKS_PATH = "memberaudit.tasks"


class TestUILauncher(WebTest):
    fixtures = ["disable_analytics.json"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        reset_celery_once_locks()

    def setUp(self) -> None:
        self.user, _ = create_user_from_evecharacter_with_access(1002)

    def test_open_character_viewer(self):
        """
        given user has character registered
        when clicking on respective character link
        then user is forwarded to character viewer
        """
        # setup
        character = add_memberaudit_character_to_user(self.user, 1001)

        # login & open launcher page
        self.app.set_user(self.user)
        launcher = self.app.get(reverse("memberaudit:launcher"))
        self.assertEqual(launcher.status_code, 200)

        # user clicks on character link
        character_viewer = launcher.click(
            href=reverse("memberaudit:character_viewer", args=[character.pk]),
            index=0,  # follow the first matching link
        )
        self.assertEqual(character_viewer.status_code, 200)

    @patch(MANAGERS_PATH + ".character_sections_1.esi", esi_stub)
    @patch(MANAGERS_PATH + ".character_sections_2.esi", esi_stub)
    @patch(MANAGERS_PATH + ".character_sections_3.esi", esi_stub)
    @patch(MANAGERS_PATH + ".general.esi", esi_stub)
    @override_settings(
        CELERY_ALWAYS_EAGER=True,
        CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
        APP_UTILS_OBJECT_CACHE_DISABLED=True,
    )
    def test_add_character(self):
        """
        when clicking on "register"
        then user can add a new character
        """
        # user as another auth character
        character_ownership_1001 = add_auth_character_to_user(self.user, 1001)

        # login & open launcher page
        self.app.set_user(self.user)
        launcher = self.app.get(reverse("memberaudit:launcher"))
        self.assertEqual(launcher.status_code, 200)

        # user clicks on register link
        select_token = launcher.click(
            href=reverse("memberaudit:add_character"),
            index=1,  # follow the 2nd matching link
        )
        self.assertEqual(select_token.status_code, 200)

        # user selects auth character 1001
        token = self.user.token_set.get(character_id=1001)
        my_form = None
        for form in select_token.forms.values():
            try:
                if int(form["_token"].value) == token.pk:
                    my_form = form
                    break
            except AssertionError:
                pass

        self.assertIsNotNone(my_form)
        launcher = my_form.submit().follow()
        self.assertEqual(launcher.status_code, 200)

        # check update went through
        character_1001 = character_ownership_1001.character.memberaudit_character
        self.assertTrue(character_1001.is_update_status_ok())

        # check added character is now visible in launcher
        a_tags = launcher.html.find_all("a", href=True)
        viewer_url = reverse("memberaudit:character_viewer", args=[character_1001.pk])
        character_1001_links = [
            a_tag["href"] for a_tag in a_tags if a_tag["href"] == viewer_url
        ]
        self.assertGreater(len(character_1001_links), 0)

    def test_share_character_1(self):
        """
        when user has share permission
        then he can share his characters
        """
        # setup
        character_1001 = add_memberaudit_character_to_user(self.user, 1001)
        self.user = AuthUtils.add_permission_to_user_by_name(
            "memberaudit.share_characters", self.user
        )

        # login & open launcher page
        self.app.set_user(self.user)
        launcher = self.app.get(reverse("memberaudit:launcher"))
        self.assertEqual(launcher.status_code, 200)

        # check for share button
        share_url = reverse("memberaudit:share_character", args=[character_1001.pk])
        a_tags = launcher.html.find_all("a", href=True)
        character_1001_links = [
            a_tag["href"] for a_tag in a_tags if a_tag["href"] == share_url
        ]
        self.assertGreater(len(character_1001_links), 0)

    def test_share_character_2(self):
        """
        when user does not have share permission
        then he can not share his characters
        """
        # setup
        character_1001 = add_memberaudit_character_to_user(self.user, 1001)

        # login & open launcher page
        self.app.set_user(self.user)
        launcher = self.app.get(reverse("memberaudit:launcher"))
        self.assertEqual(launcher.status_code, 200)

        # check for share button
        share_url = reverse("memberaudit:share_character", args=[character_1001.pk])
        a_tags = launcher.html.find_all("a", href=True)
        character_1001_links = [
            a_tag["href"] for a_tag in a_tags if a_tag["href"] == share_url
        ]
        self.assertEqual(len(character_1001_links), 0)


class TestUICharacterViewer(WebTest):
    fixtures = ["disable_analytics.json"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character = create_memberaudit_character(1001)
        cls.user = cls.character.eve_character.character_ownership.user
        cls.jita_44 = Location.objects.get(id=60003760)

    def test_asset_container(self):
        """
        given user has a registered character with assets which contain other assets
        when user clicks on an asset container
        then the contents of that asset container are shown
        """
        # setup data
        parent_asset = create_character_asset(
            character=self.character,
            location=self.jita_44,
            eve_type=EveType.objects.get(name="Charon"),
        )
        create_character_asset(
            character=self.character,
            parent=parent_asset,
            eve_type=EveType.objects.get(name="Merlin"),
        )

        # open character viewer
        self.app.set_user(self.user)
        character_viewer = self.app.get(
            reverse("memberaudit:character_viewer", args=[self.character.pk])
        )
        self.assertEqual(character_viewer.status_code, 200)

        # open asset container
        asset_container = self.app.get(
            reverse(
                "memberaudit:character_asset_container",
                args=[self.character.pk, parent_asset.pk],
            )
        )
        self.assertEqual(asset_container.status_code, 200)
        self.assertIn("Asset Container", asset_container.text)

    def test_contract_items(self):
        """
        given user has a registered character with contracts that contain items
        when user clicks to open the contract
        then the items of that contact are shown
        """
        # setup data
        contract = create_character_contract(
            character=self.character,
            contract_type=CharacterContract.TYPE_ITEM_EXCHANGE,
            start_location=self.jita_44,
            end_location=self.jita_44,
        )
        create_character_contract_item(
            contract=contract,
            eve_type=EveType.objects.get(name="High-grade Snake Alpha"),
        )

        # open character viewer
        self.app.set_user(self.user)
        character_viewer = self.app.get(
            reverse("memberaudit:character_viewer", args=[self.character.pk])
        )
        self.assertEqual(character_viewer.status_code, 200)

        # open asset container
        contract_details = self.app.get(
            reverse(
                "memberaudit:character_contract_details",
                args=[self.character.pk, contract.pk],
            )
        )
        self.assertEqual(contract_details.status_code, 200)
        self.assertIn("High-grade Snake Alpha", contract_details.text)

    def test_mail(self):
        """
        given user has a registered character with mails
        when user clicks to open a mail
        then the mail body is shown
        """
        # setup data
        body_text = "My text body"
        label = create_character_mail_label(character=self.character)
        sender_1002, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1002)
        mail = create_character_mail(
            character=self.character, sender=sender_1002, body=body_text
        )
        recipient_1001, _ = MailEntity.objects.update_or_create_from_eve_entity_id(
            id=1001
        )
        recipient_1003, _ = MailEntity.objects.update_or_create_from_eve_entity_id(
            id=1003
        )
        mail.recipients.add(recipient_1001, recipient_1003)
        mail.labels.add(label)

        # open character viewer
        self.app.set_user(self.user)
        character_viewer = self.app.get(
            reverse("memberaudit:character_viewer", args=[self.character.pk])
        )
        self.assertEqual(character_viewer.status_code, 200)

        # open mail
        mail_details = self.app.get(
            reverse("memberaudit:character_mail", args=[self.character.pk, mail.pk])
        )
        self.assertEqual(mail_details.status_code, 200)
        self.assertIn(body_text, mail_details.text)


@patch(
    TASKS_PATH + ".Character.objects.get_cached",
    lambda pk, timeout: Character.objects.get(pk=pk),
)
@patch(MANAGERS_PATH + ".general.fetch_esi_status", lambda: EsiStatus(True, 99, 60))
@patch(MANAGERS_PATH + ".character_sections_1.esi", esi_stub)
@patch(MANAGERS_PATH + ".character_sections_2.esi", esi_stub)
@patch(MANAGERS_PATH + ".character_sections_3.esi", esi_stub)
@patch(MANAGERS_PATH + ".general.esi", esi_stub)
@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
class TestAdminSite(TestCase):
    fixtures = ["disable_analytics.json"]

    @classmethod
    def setUpTestData(cls) -> None:
        load_eveuniverse()
        load_entities()
        cls.user = UserFactory(is_staff=True, is_superuser=True)
        reset_celery_once_locks()

    def test_should_delete_selected_characters(self):
        # given 2 characters
        character_1001 = create_memberaudit_character(1001)
        character_1002 = create_memberaudit_character(1002)
        character_1003 = create_memberaudit_character(1003)
        self.client.force_login(self.user)

        # when selected 2 characters for deletion
        response = self.client.post(
            "/admin/memberaudit/character/",
            data={
                "action": "delete_objects",
                "select_across": 0,
                "index": 0,
                "_selected_action": [character_1001.pk, character_1002.pk],
            },
        )

        # then user is asked to confirm the 2 selected characters
        self.assertEqual(response.status_code, 200)
        text = response.content.decode("utf-8")
        self.assertIn(str(character_1001), text)
        self.assertIn(str(character_1002), text)
        self.assertNotIn(str(character_1003), text)

        # when user clicked on confirm
        response = self.client.post(
            "/admin/memberaudit/character/",
            data={
                "action": "delete_objects",
                "apply": "Delete",
                "_selected_action": [character_1001.pk, character_1002.pk],
            },
        )

        # then the selected characters are deleted, but the other character remains
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/admin/memberaudit/character/")
        self.assertFalse(
            Character.objects.filter(
                pk__in=[character_1001.pk, character_1002.pk]
            ).exists()
        )
        self.assertTrue(Character.objects.filter(pk=character_1003.pk).exists())

    def test_should_delete_selected_skill_sets(self):
        # given 3 objects
        obj_1 = create_skill_set()
        obj_2 = create_skill_set()
        obj_3 = create_skill_set()
        self.client.force_login(self.user)

        # when user selects 2 for deletion
        response = self.client.post(
            "/admin/memberaudit/skillset/",
            data={
                "action": "delete_objects",
                "apply": "Delete",
                "_selected_action": [obj_1.pk, obj_2.pk],
            },
        )

        # then the selected objects are deleted, but the other object remains
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/admin/memberaudit/skillset/")
        self.assertFalse(SkillSet.objects.filter(pk__in=[obj_1.pk, obj_2.pk]).exists())
        self.assertTrue(SkillSet.objects.filter(pk=obj_3.pk).exists())

    def test_should_update_location_for_characters(self):
        # given 2 characters
        character_1001 = create_memberaudit_character(1001)
        self.client.force_login(self.user)

        # when user starts action
        self.client.post(
            "/admin/memberaudit/character/",
            data={
                "action": "update_section_location",
                "_selected_action": [character_1001.pk],
            },
        )

        # then character is updated
        self.assertEqual(character_1001.location.location.eve_solar_system.name, "Jita")

    def test_should_update_assets_for_characters(self):
        # given 2 characters
        character_1001 = create_memberaudit_character(1001)
        self.client.force_login(self.user)

        # when user starts action
        self.client.post(
            "/admin/memberaudit/character/",
            data={
                "action": "update_assets",
                "_selected_action": [character_1001.pk],
            },
        )

        # then character is updated
        character_1001.refresh_from_db()
        self.assertTrue(character_1001.assets.exists())


@patch(
    TASKS_PATH + ".Character.objects.get_cached",
    lambda pk, timeout: Character.objects.get(pk=pk),
)
@patch(MANAGERS_PATH + ".general.fetch_esi_status", lambda: EsiStatus(True, 99, 60))
@patch(TASKS_PATH + ".MEMBERAUDIT_LOG_UPDATE_STATS", False)
@patch(MANAGERS_PATH + ".character_sections_1.data_retention_cutoff", lambda: None)
@patch(MANAGERS_PATH + ".character_sections_2.data_retention_cutoff", lambda: None)
@patch(MANAGERS_PATH + ".character_sections_3.data_retention_cutoff", lambda: None)
@patch(MANAGERS_PATH + ".character_sections_1.esi", esi_stub)
@patch(MANAGERS_PATH + ".character_sections_2.esi", esi_stub)
@patch(MANAGERS_PATH + ".character_sections_3.esi", esi_stub)
@patch(MANAGERS_PATH + ".general.esi", esi_stub)
@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    APP_UTILS_OBJECT_CACHE_DISABLED=True,
)
class TestTasksIntegration(TestCase):
    fixtures = ["disable_analytics.json"]

    @classmethod
    def setUpTestData(cls) -> None:
        load_eveuniverse()
        load_entities()
        load_locations()
        reset_celery_once_locks()

    def test_should_update_all_characters(self):
        # given
        character_1001 = create_memberaudit_character(1001)
        # when
        tasks.update_all_characters()
        # then
        self.assertTrue(character_1001.is_update_status_ok())


@patch(MANAGERS_PATH + ".character_sections_2.esi")
@patch(MANAGERS_PATH + ".general.esi")
class TestCharacterMailUpdate(NoSocketsTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        load_entities()
        cls.character = create_memberaudit_character(1001)

    @staticmethod
    def stub_eve_entity_get_or_create_esi(id, *args, **kwargs):
        """will return EveEntity if it exists else None, False"""
        try:
            obj = EveEntity.objects.get(id=id)
            return obj, True
        except EveEntity.DoesNotExist:
            return None, False

    @patch(MANAGERS_PATH + ".character_sections_2.data_retention_cutoff", lambda: None)
    @patch(MANAGERS_PATH + ".character_sections_2.EveEntity.objects.get_or_create_esi")
    def test_should_update_existing_mail_headers(
        self,
        mock_eve_entity,
        mock_esi_character,
        mock_esi_sections,
    ):
        # given
        mock_esi_character.client = esi_client_stub
        mock_esi_sections.client = esi_client_stub
        mock_eve_entity.side_effect = self.stub_eve_entity_get_or_create_esi
        sender, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1002)
        mail = create_character_mail(
            character=self.character,
            mail_id=1,
            sender=sender,
            subject="Mail 1",
            body="My body text",
            timestamp=parse_datetime("2015-09-05T16:07:00Z"),
            is_read=False,  # to be updated
        )
        recipient_1, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=1001)
        recipient_2 = create_mailing_list()
        mail.recipients.set([recipient_1, recipient_2])

        self.character.update_mailing_lists()
        self.character.update_mail_labels()

        label = self.character.mail_labels.get(label_id=17)
        mail.labels.add(label)  # to be updated

        # when
        self.character.update_mail_headers()

        # then
        self.assertSetEqual(
            set(self.character.mails.values_list("mail_id", flat=True)),
            {1, 2, 3},
        )

        obj = self.character.mails.get(mail_id=1)
        self.assertEqual(obj.sender_id, 1002)
        self.assertTrue(obj.is_read)
        self.assertEqual(obj.subject, "Mail 1")
        self.assertEqual(obj.timestamp, parse_datetime("2015-09-05T16:07:00Z"))
        self.assertEqual(obj.body, "My body text")
        recipient_ids = set(obj.recipients.values_list("id", flat=True))
        self.assertSetEqual(recipient_ids, {recipient_1.id, recipient_2.id})
        label_ids = set(obj.labels.values_list("label_id", flat=True))
        self.assertSetEqual(label_ids, {3})
