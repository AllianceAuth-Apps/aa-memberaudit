from http import HTTPStatus

from django.urls import reverse
from django_webtest import WebTest

from app_utils.testdata_factories import UserMainFactory

from memberaudit.tests.testdata.factories_2 import (
    CharacterAssetFactory,
    CharacterContractItemExchangeFactory,
    CharacterContractItemFactory,
    CharacterFactory,
    CharacterMailFactory,
    LocationStationFactory,
    UserMainBasicAccessFactory,
)


class TestUILauncher(WebTest):
    fixtures = ["disable_analytics.json"]

    def test_open_character_viewer(self):
        """
        given user has character registered
        when clicking on respective character link
        then user is forwarded to character viewer
        """
        # setup
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user)

        # login & open launcher page
        self.app.set_user(user)
        launcher = self.app.get(reverse("memberaudit:launcher"))
        self.assertEqual(launcher.status_code, HTTPStatus.OK)

        # user clicks on character link
        character_viewer = launcher.click(
            href=reverse("memberaudit:character_viewer", args=[character.pk]),
            index=0,  # follow the first matching link
        )
        self.assertEqual(character_viewer.status_code, HTTPStatus.OK)

    def test_share_character_1(self):
        """
        when user has share permission
        then he can share his characters
        """
        # setup
        user = UserMainFactory(
            permissions__=["memberaudit.basic_access", "memberaudit.share_characters"]
        )
        character = CharacterFactory(user=user)

        # login & open launcher page
        self.app.set_user(user)
        launcher = self.app.get(reverse("memberaudit:launcher"))
        self.assertEqual(launcher.status_code, HTTPStatus.OK)

        # check for share button
        share_url = reverse("memberaudit:share_character", args=[character.pk])
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
        user = UserMainFactory(permissions__=["memberaudit.basic_access"])
        character = CharacterFactory(user=user)

        # login & open launcher page
        self.app.set_user(user)
        launcher = self.app.get(reverse("memberaudit:launcher"))
        self.assertEqual(launcher.status_code, HTTPStatus.OK)

        # check for share button
        share_url = reverse("memberaudit:share_character", args=[character.pk])
        a_tags = launcher.html.find_all("a", href=True)
        character_1001_links = [
            a_tag["href"] for a_tag in a_tags if a_tag["href"] == share_url
        ]
        self.assertEqual(len(character_1001_links), 0)


class TestUICharacterViewer(WebTest):
    fixtures = ["disable_analytics.json"]

    def test_asset_container(self):
        """
        given user has a registered character with assets which contain other assets
        when user clicks on an asset container
        then the contents of that asset container are shown
        """
        # setup data
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user)
        station = LocationStationFactory()
        parent_asset = CharacterAssetFactory(character=character, location=station)
        CharacterAssetFactory(character=character, parent=parent_asset)

        # open character viewer
        self.app.set_user(user)
        character_viewer = self.app.get(
            reverse("memberaudit:character_viewer", args=[character.pk])
        )
        self.assertEqual(character_viewer.status_code, HTTPStatus.OK)

        # open asset container
        asset_container = self.app.get(
            reverse(
                "memberaudit:character_asset_container",
                args=[character.pk, parent_asset.pk],
            )
        )
        self.assertEqual(asset_container.status_code, HTTPStatus.OK)
        self.assertIn("Asset Container", asset_container.text)

    def test_contract_items(self):
        """
        given user has a registered character with contracts that contain items
        when user clicks to open the contract
        then the items of that contact are shown
        """
        # setup data
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user)
        contract = CharacterContractItemExchangeFactory(
            character=character, items=False
        )
        item = CharacterContractItemFactory(contract=contract)

        # open character viewer
        self.app.set_user(user)
        character_viewer = self.app.get(
            reverse("memberaudit:character_viewer", args=[character.pk])
        )
        self.assertEqual(character_viewer.status_code, HTTPStatus.OK)

        # open contract details
        contract_details = self.app.get(
            reverse(
                "memberaudit:character_contract_details",
                args=[character.pk, contract.pk],
            )
        )
        self.assertEqual(contract_details.status_code, HTTPStatus.OK)
        self.assertIn(item.eve_type.name, contract_details.text)

    def test_mail(self):
        """
        given user has a registered character with mails
        when user clicks to open a mail
        then the mail body is shown
        """
        # setup data
        user = UserMainBasicAccessFactory()
        character = CharacterFactory(user=user)
        body_text = "My text body"
        mail = CharacterMailFactory(character=character, body=body_text)

        # open character viewer
        self.app.set_user(user)
        character_viewer = self.app.get(
            reverse("memberaudit:character_viewer", args=[character.pk])
        )
        self.assertEqual(character_viewer.status_code, HTTPStatus.OK)

        # open mail
        mail_details = self.app.get(
            reverse("memberaudit:character_mail", args=[character.pk, mail.pk])
        )
        self.assertEqual(mail_details.status_code, HTTPStatus.OK)
        self.assertIn(body_text, mail_details.text)
