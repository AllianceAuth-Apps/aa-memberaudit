import datetime as dt
from http import HTTPStatus
from unittest.mock import patch

import pook

from django.utils.timezone import now
from eveuniverse.tests.testdata.factories_2 import EveEntityCorporationFactory

from app_utils.testing import NoSocketsTestCase

from memberaudit.models import (
    CharacterLocation,
    CharacterLoyaltyEntry,
    CharacterMail,
    CharacterMailLabel,
    MailEntity,
)
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterLocationFactory,
    CharacterLoyaltyEntryFactory,
    CharacterMailFactory,
    CharacterMailLabelFactory,
    LocationSolarSystemFactory,
    LocationStationFactory,
    LocationStructureFactory,
    MailEntityCharacterFactory,
    MailEntityMailingListFactory,
    make_esi_url,
)
from memberaudit.tests.utils import TestCaseWithClearCache, extract

MODULE_PATH = "memberaudit.managers.character_sections_2"


class TestCharacter_UpdateLocation(TestCaseWithClearCache):
    @pook.on
    def test_should_create_location_from_scratch_for_station(self):
        # given
        character = CharacterFactory()
        location = LocationStationFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/location"),
            reply=HTTPStatus.OK,
            response_json={
                "solar_system_id": location.eve_solar_system.id,
                "station_id": location.id,
            },
        )

        # when
        character.update_location()

        # then
        obj: CharacterLocation = character.location
        self.assertEqual(obj.eve_solar_system, location.eve_solar_system)
        self.assertEqual(obj.location, location)

    @pook.on
    def test_should_create_location_from_scratch_for_structure(self):
        # given
        character = CharacterFactory()
        location = LocationStructureFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/location"),
            reply=HTTPStatus.OK,
            response_json={
                "solar_system_id": location.eve_solar_system.id,
                "structure_id": location.id,
            },
        )

        # when
        character.update_location()

        # then
        obj: CharacterLocation = character.location
        self.assertEqual(obj.eve_solar_system, location.eve_solar_system)
        self.assertEqual(obj.location, location)

    @pook.on
    def test_should_create_location_from_scratch_for_solar_system(self):
        # given
        character = CharacterFactory()
        location = LocationSolarSystemFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/location"),
            reply=HTTPStatus.OK,
            response_json={
                "solar_system_id": location.id,
            },
        )

        # when
        character.update_location()

        # then
        obj: CharacterLocation = character.location
        self.assertEqual(obj.eve_solar_system, location.eve_solar_system)
        self.assertEqual(obj.location, location)

    @pook.on
    def test_should_update_location(self):
        # given
        character = CharacterFactory()
        character_location = CharacterLocationFactory(character=character)
        location = LocationStationFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/location"),
            reply=HTTPStatus.OK,
            response_json={
                "solar_system_id": location.eve_solar_system.id,
                "station_id": location.id,
            },
        )

        # when
        character.update_location()

        # then
        character_location.refresh_from_db()
        self.assertEqual(character_location.eve_solar_system, location.eve_solar_system)
        self.assertEqual(character_location.location, location)


class TestCharacter_UpdateLoyalty(TestCaseWithClearCache):
    @pook.on
    def test_can_create_from_scratch(self):
        # given
        character = CharacterFactory()
        corporation = EveEntityCorporationFactory()
        loyalty_points = 42
        pook.get(
            make_esi_url(f"characters/{character.character_id}/loyalty/points"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "corporation_id": corporation.id,
                    "loyalty_points": loyalty_points,
                }
            ],
        )
        # when
        character.update_loyalty()

        # then
        self.assertEqual(character.loyalty_entries.count(), 1)
        obj: CharacterLoyaltyEntry = character.loyalty_entries.first()
        self.assertEqual(obj.corporation, corporation)
        self.assertEqual(obj.loyalty_points, loyalty_points)

    @pook.on
    def test_can_update_existing_entries(self):
        # given
        character = CharacterFactory()
        entry = CharacterLoyaltyEntryFactory(character=character)
        loyalty_points = 42
        pook.get(
            make_esi_url(f"characters/{character.character_id}/loyalty/points"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "corporation_id": entry.corporation.id,
                    "loyalty_points": loyalty_points,
                }
            ],
        )
        # when
        character.update_loyalty()

        # then
        entry.refresh_from_db()
        self.assertEqual(entry.loyalty_points, loyalty_points)

    @pook.on
    def test_can_remove_stale_entries(self):
        # given
        character = CharacterFactory()
        CharacterLoyaltyEntryFactory(character=character)  # to be removed
        corporation = EveEntityCorporationFactory()
        loyalty_points = 42
        pook.get(
            make_esi_url(f"characters/{character.character_id}/loyalty/points"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "corporation_id": corporation.id,
                    "loyalty_points": loyalty_points,
                }
            ],
        )
        # when
        character.update_loyalty()

        # then
        self.assertEqual(character.loyalty_entries.count(), 1)
        obj: CharacterLoyaltyEntry = character.loyalty_entries.first()
        self.assertEqual(obj.corporation, corporation)

    @pook.on
    def test_should_ignore_http_500(self):
        # given
        character = CharacterFactory()
        entry = CharacterLoyaltyEntryFactory(character=character)  # to be kept
        pook.get(
            make_esi_url(f"characters/{character.character_id}/loyalty/points"),
            reply=500,
            response_json={"error": "some error"},
        )
        # when
        character.update_loyalty()

        # then
        self.assertEqual(character.loyalty_entries.count(), 1)
        obj: CharacterLoyaltyEntry = character.loyalty_entries.first()
        self.assertEqual(obj.corporation, entry.corporation)


class TestCharacter_UpdateMailHeaders(TestCaseWithClearCache):
    @pook.on
    def test_can_create_new_mail_without_labels(self):
        # given
        character = CharacterFactory()
        sender = MailEntityCharacterFactory()
        recipient = MailEntityCharacterFactory()
        subject = "subject"
        mail_id = 42
        timestamp = now()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "from": sender.id,
                    "is_read": True,
                    "labels": [],
                    "mail_id": mail_id,
                    "recipients": [
                        {"recipient_id": recipient.id, "recipient_type": "character"},
                    ],
                    "subject": subject,
                    "timestamp": timestamp.isoformat(),
                }
            ],
        )

        # when
        character.update_mail_headers()

        # then
        self.assertEqual(character.mails.count(), 1)
        obj: CharacterMail = character.mails.first()
        self.assertEqual(obj.is_read, True)
        self.assertEqual(obj.mail_id, mail_id)
        self.assertEqual(obj.sender, sender)
        self.assertEqual(obj.subject, subject)
        self.assertEqual(obj.timestamp, timestamp)
        self.assertFalse(obj.body)

        self.assertSetEqual(extract(obj.recipients, "id"), {recipient.id})

    @pook.on
    def test_can_create_new_mail_with_labels(self):
        # given
        character = CharacterFactory()
        label = CharacterMailLabelFactory(character=character)
        sender = MailEntityCharacterFactory()
        recipient = MailEntityCharacterFactory()
        subject = "subject"
        mail_id = 42
        timestamp = now()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "from": sender.id,
                    "is_read": True,
                    "labels": [label.label_id],
                    "mail_id": mail_id,
                    "recipients": [
                        {"recipient_id": recipient.id, "recipient_type": "character"},
                    ],
                    "subject": subject,
                    "timestamp": timestamp.isoformat(),
                }
            ],
        )

        # when
        character.update_mail_headers()

        # then
        self.assertEqual(character.mails.count(), 1)
        obj: CharacterMail = character.mails.first()
        self.assertEqual(obj.is_read, True)
        self.assertEqual(obj.mail_id, mail_id)
        self.assertEqual(obj.sender, sender)
        self.assertEqual(obj.subject, subject)
        self.assertEqual(obj.timestamp, timestamp)
        self.assertFalse(obj.body)

        self.assertSetEqual(extract(obj.recipients, "id"), {recipient.id})
        self.assertSetEqual(extract(obj.labels, "label_id"), {label.label_id})

    @pook.on
    def test_should_keep_mail_not_returned_from_esi(self):
        # given
        character = CharacterFactory()
        mail_1 = CharacterMailFactory(character=character)
        sender = MailEntityCharacterFactory()
        recipient = MailEntityCharacterFactory()
        subject_2 = "subject"
        mail_2_id = 42
        timestamp_2 = now()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "from": sender.id,
                    "is_read": True,
                    "labels": [],
                    "mail_id": mail_2_id,
                    "recipients": [
                        {"recipient_id": recipient.id, "recipient_type": "character"},
                    ],
                    "subject": subject_2,
                    "timestamp": timestamp_2.isoformat(),
                }
            ],
        )

        # when
        character.update_mail_headers()

        # given
        got = extract(character.mails, "mail_id")
        self.assertSetEqual(got, {mail_2_id, mail_1.mail_id})

    @pook.on
    def test_should_ignore_and_delete_older_mail_when_data_retention_is_active(self):
        # given
        cutoff = now() - dt.timedelta(days=90)
        character = CharacterFactory()
        sender = MailEntityCharacterFactory()
        recipient = MailEntityCharacterFactory()
        subject = "subject"
        mail_1_id = 1
        timestamp_1 = cutoff - dt.timedelta(seconds=1)
        mail_2_id = 2
        timestamp_2 = now()
        CharacterMailFactory(
            character=character, mail_id=3, timestamp=cutoff - dt.timedelta(seconds=1)
        )  # to be removed
        mail_4 = CharacterMailFactory(character=character, mail_id=4)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail"),
            reply=HTTPStatus.OK,
            response_json=[
                {
                    "from": sender.id,
                    "is_read": True,
                    "labels": [],
                    "mail_id": mail_2_id,
                    "recipients": [
                        {"recipient_id": recipient.id, "recipient_type": "character"},
                    ],
                    "subject": subject,
                    "timestamp": timestamp_2.isoformat(),
                },
                {
                    "from": sender.id,
                    "is_read": True,
                    "labels": [],
                    "mail_id": mail_1_id,
                    "recipients": [
                        {"recipient_id": recipient.id, "recipient_type": "character"},
                    ],
                    "subject": subject,
                    "timestamp": timestamp_1.isoformat(),
                },
            ],
        )

        # when
        with patch(MODULE_PATH + ".data_retention_cutoff", lambda: cutoff):
            character.update_mail_headers()

        # then
        got = extract(character.mails, "mail_id")
        self.assertSetEqual(got, {mail_2_id, mail_4.mail_id})


class TestCharacter_UpdateMailBody(TestCaseWithClearCache):
    @pook.on
    def test_should_update_existing_mail_body(self):
        # given
        character = CharacterFactory()
        mail = CharacterMailFactory(character=character)
        recipient = mail.recipients.first()
        body = "blah blah blah 😓"
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/{mail.mail_id}"),
            reply=HTTPStatus.OK,
            response_json={
                "body": body,
                "from": mail.sender.id,
                "labels": [],
                "read": mail.is_read,
                "recipients": [
                    {"recipient_id": recipient.id, "recipient_type": "character"}
                ],
                "subject": mail.subject,
                "timestamp": mail.timestamp.isoformat(),
            },
        )

        # when
        got = character.update_mail_body(mail)

        # then
        self.assertTrue(got.is_changed)
        self.assertTrue(got.is_updated)
        mail.refresh_from_db()
        self.assertEqual(mail.body, body)

    @pook.on
    def test_should_not_update_when_body_has_not_changed(self):
        # given
        character = CharacterFactory()
        mail = CharacterMailFactory(character=character)
        body = mail.body
        recipient = mail.recipients.first()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/{mail.mail_id}"),
            reply=HTTPStatus.OK,
            response_json={
                "body": mail.body,
                "from": mail.sender.id,
                "labels": [],
                "read": mail.is_read,
                "recipients": [
                    {"recipient_id": recipient.id, "recipient_type": "character"}
                ],
                "subject": mail.subject,
                "timestamp": mail.timestamp.isoformat(),
            },
        )

        # when
        got = character.update_mail_body(mail)

        # then
        self.assertFalse(got.is_changed)
        self.assertFalse(got.is_updated)
        mail.refresh_from_db()
        self.assertEqual(mail.body, body)

    @pook.on
    def test_should_update_when_body_has_not_changed_but_forced(self):
        # given
        character = CharacterFactory()
        mail = CharacterMailFactory(character=character)
        body = mail.body
        recipient = mail.recipients.first()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/{mail.mail_id}"),
            reply=HTTPStatus.OK,
            response_json={
                "body": mail.body,
                "from": mail.sender.id,
                "labels": [],
                "read": mail.is_read,
                "recipients": [
                    {"recipient_id": recipient.id, "recipient_type": "character"}
                ],
                "subject": mail.subject,
                "timestamp": mail.timestamp.isoformat(),
            },
        )

        # when
        got = character.update_mail_body(mail, force_update=True)

        # then
        self.assertFalse(got.is_changed)
        self.assertTrue(got.is_updated)
        mail.refresh_from_db()
        self.assertEqual(mail.body, body)

    @pook.on
    def test_should_delete_mail_when_fetching_body_returns_404(self):
        # given
        character = CharacterFactory()
        mail = CharacterMailFactory(character=character)
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/{mail.mail_id}"),
            reply=HTTPStatus.NOT_FOUND,
            response_json={"error": "not found"},
        )

        # when
        got = character.update_mail_body(mail)
        self.assertTrue(got.is_changed)
        self.assertTrue(got.is_updated)
        self.assertFalse(character.mails.filter(mail_id=mail.mail_id).exists())

    @pook.on
    def test_can_fetch_mails_with_paging(self):
        # given
        character = CharacterFactory()
        sender = MailEntityCharacterFactory()
        recipient = MailEntityCharacterFactory()
        last_mail_id = 1_000
        timestamp = now()
        mails = []
        for _ in range(60):
            mails.append(
                {
                    "from": sender.id,
                    "is_read": False,
                    "labels": [],
                    "mail_id": last_mail_id,
                    "recipients": [
                        {"recipient_id": recipient.id, "recipient_type": "character"},
                    ],
                    "subject": f"subject {last_mail_id}",
                    "timestamp": (timestamp - dt.timedelta(seconds=1)).isoformat(),
                }
            )
            last_mail_id -= 1

        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail"),
            reply=HTTPStatus.OK,
            response_json=mails[:50],
        )
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail"),
            reply=HTTPStatus.OK,
            response_json=mails[50:],
        )

        # when
        character.update_mail_headers()

        # then
        self.assertEqual(character.mails.count(), 60)


class TestCharacter_UpdateMailLabels(TestCaseWithClearCache):
    @pook.on
    def test_should_create_labels_from_scratch(self):
        # given
        character = CharacterFactory()
        total_unread_count = 5
        unread_count = 4
        color = "#660066"
        name = "Special"
        label_id = 42
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/labels"),
            reply=HTTPStatus.OK,
            response_json={
                "labels": [
                    {
                        "color": color,
                        "label_id": label_id,
                        "name": name,
                        "unread_count": unread_count,
                    }
                ],
                "total_unread_count": total_unread_count,
            },
        )

        # when
        character.update_mail_labels()

        # then
        self.assertEqual(character.unread_mail_count.total, total_unread_count)
        self.assertEqual(character.mail_labels.count(), 1)
        obj: CharacterMailLabel = character.mail_labels.first()
        self.assertEqual(obj.name, name)
        self.assertEqual(obj.unread_count, unread_count)
        self.assertEqual(obj.color, color)
        self.assertEqual(obj.label_id, label_id)

    @pook.on
    def test_should_update_existing_labels(self):
        # given
        character = CharacterFactory()
        label = CharacterMailLabelFactory(character=character)
        total_unread_count = 5
        unread_count = 4
        color = "#660066"
        name = "Special"
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/labels"),
            reply=HTTPStatus.OK,
            response_json={
                "labels": [
                    {
                        "color": color,
                        "label_id": label.label_id,
                        "name": name,
                        "unread_count": unread_count,
                    }
                ],
                "total_unread_count": total_unread_count,
            },
        )

        # when
        character.update_mail_labels()

        # then
        self.assertEqual(character.unread_mail_count.total, total_unread_count)

        label.refresh_from_db()
        self.assertEqual(label.name, name)
        self.assertEqual(label.unread_count, unread_count)
        self.assertEqual(label.color, color)

    @pook.on
    def test_should_remove_stale_labels(self):
        # given
        character = CharacterFactory()
        CharacterMailLabelFactory(character=character)  # to be removed
        total_unread_count = 5
        unread_count = 4
        color = "#660066"
        name = "Special"
        label_id = 42
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/labels"),
            reply=HTTPStatus.OK,
            response_json={
                "labels": [
                    {
                        "color": color,
                        "label_id": label_id,
                        "name": name,
                        "unread_count": unread_count,
                    }
                ],
                "total_unread_count": total_unread_count,
            },
        )

        # when
        character.update_mail_labels()

        # then
        got = extract(character.mail_labels, "label_id")
        want = {label_id}
        self.assertSetEqual(got, want)


class TestCharacter_UpdateMailingLists(TestCaseWithClearCache):
    @pook.on
    def test_can_create_new_mailing_list(self):
        """can create new mailing lists from scratch"""
        # given
        character = CharacterFactory()
        mailing_list_id = 9001
        name = "Alpha"
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/lists"),
            reply=HTTPStatus.OK,
            response_json=[{"mailing_list_id": mailing_list_id, "name": name}],
        )

        # when
        character.update_mailing_lists()

        # then
        self.assertEqual(character.mailing_lists.count(), 1)
        obj: MailEntity = character.mailing_lists.first()
        self.assertEqual(obj.id, mailing_list_id)
        self.assertEqual(obj.name, name)

    @pook.on
    def test_should_remove_stale_lists_from_character_but_keep_object(self):
        # given
        character = CharacterFactory()
        mailing_list_1 = MailEntityMailingListFactory()
        character.mailing_lists.add(mailing_list_1)
        mailing_list_2_id = 9001
        name = "Alpha"
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/lists"),
            reply=HTTPStatus.OK,
            response_json=[{"mailing_list_id": mailing_list_2_id, "name": name}],
        )

        # when
        character.update_mailing_lists()

        # then
        got_1 = extract(character.mailing_lists, "id")
        want_1 = {mailing_list_2_id}
        self.assertSetEqual(got_1, want_1)

        got_2 = extract(MailEntity.objects, "id")
        want_2 = {mailing_list_1.id, mailing_list_2_id}
        self.assertSetEqual(got_2, want_2)

    @pook.on
    def test_can_update_existing_mailing_list(self):
        # given
        character = CharacterFactory()
        obj = MailEntityMailingListFactory()
        name = "new name"
        pook.get(
            make_esi_url(f"characters/{character.character_id}/mail/lists"),
            reply=HTTPStatus.OK,
            response_json=[{"mailing_list_id": obj.id, "name": name}],
        )

        # when
        character.update_mailing_lists()

        # then
        obj.refresh_from_db()
        self.assertEqual(obj.name, name)


class TestCharacterMailLabelManager_GetAllLabels(NoSocketsTestCase):
    def test_should_return_labels_for_all_characters(self):
        # given
        label_1 = CharacterMailLabelFactory()
        label_2 = CharacterMailLabelFactory()

        # when
        got = CharacterMailLabel.objects.get_all_labels()

        # then
        want = {label_1.label_id: label_1, label_2.label_id: label_2}
        self.assertDictEqual(got, want)

    def test_should_return_empty_when_no_labels_exist(self):
        # when
        got = CharacterMailLabel.objects.get_all_labels()

        # then
        want = {}
        self.assertDictEqual(got, want)
