from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from django_webtest import WebTest
from eveuniverse.models import EveType

from allianceauth.tests.auth_utils import AuthUtils

from memberaudit.models import Character, CharacterContract, Location, MailEntity
from memberaudit.tests.testdata.esi_client_stub import esi_stub
from memberaudit.tests.testdata.factories import (
    create_character_asset,
    create_character_contract,
    create_character_contract_item,
    create_character_mail,
    create_character_mail_label,
)
from memberaudit.tests.testdata.load_entities import load_entities
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse
from memberaudit.tests.testdata.load_locations import load_locations
from memberaudit.tests.utils import (
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
        character_1001: Character = (
            character_ownership_1001.character.memberaudit_character
        )
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
