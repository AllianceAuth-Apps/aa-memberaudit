from django.test import RequestFactory, TestCase
from django.urls import reverse

from memberaudit.models import Character, CharacterUpdateStatus
from memberaudit.templatetags.memberaudit import navactive_2, tab_status_indicator


class TestNavactive2(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_simple_return_active_when_matches(self):
        request = self.factory.get(reverse("memberaudit:add_character"))
        result = navactive_2(request, "memberaudit:add_character")
        self.assertEqual(result, "active")

    def test_simple_return_empty_when_no_match(self):
        request = self.factory.get(reverse("memberaudit:add_character"))
        result = navactive_2(request, "memberaudit:reports")
        self.assertEqual(result, "")

    def test_complex_return_active_when_matches(self):
        request = self.factory.get(reverse("memberaudit:character_viewer", args=[2]))
        result = navactive_2(request, "memberaudit:character_viewer", 2)
        self.assertEqual(result, "active")


class TestTabStatusIndicator(TestCase):
    def test_should_not_report_error_when_section_ok(self):
        # given
        status = CharacterUpdateStatus(
            section=Character.UpdateSection.LOCATION, is_success=True
        )
        sections_update_status = {"location": status}
        context = {
            "sections_update_status": sections_update_status,
            "total_update_status": Character.TotalUpdateStatus.OK,
        }
        # when
        result = tab_status_indicator(context, Character.UpdateSection.LOCATION)
        # then
        self.assertEqual(result["tab_update_status"], Character.TotalUpdateStatus.OK)

    def test_should_report_incomplete_when_section_not_found(self):
        # given
        status = CharacterUpdateStatus(
            section=Character.UpdateSection.MAILS, is_success=True
        )
        sections_update_status = {"mails": status}
        context = {
            "sections_update_status": sections_update_status,
            "total_update_status": Character.TotalUpdateStatus.OK,
        }
        # when
        result = tab_status_indicator(context, Character.UpdateSection.LOCATION)
        # then
        self.assertEqual(
            result["tab_update_status"], Character.TotalUpdateStatus.INCOMPLETE
        )

    def test_should_report_error_when_section_not_ok(self):
        # given
        status = CharacterUpdateStatus(
            section=Character.UpdateSection.LOCATION, is_success=False
        )
        sections_update_status = {"location": status}
        context = {
            "sections_update_status": sections_update_status,
            "total_update_status": Character.TotalUpdateStatus.ERROR,
        }
        # when
        result = tab_status_indicator(context, Character.UpdateSection.LOCATION)
        # then
        self.assertEqual(result["tab_update_status"], Character.TotalUpdateStatus.ERROR)

    def test_should_report_error_when_one_of_several_sections_not_ok(self):
        # given
        status_location = CharacterUpdateStatus(
            section=Character.UpdateSection.LOCATION, is_success=True
        )
        status_mails = CharacterUpdateStatus(
            section=Character.UpdateSection.LOCATION, is_success=False
        )
        sections_update_status = {"location": status_location, "mails": status_mails}
        context = {
            "sections_update_status": sections_update_status,
            "total_update_status": Character.TotalUpdateStatus.ERROR,
        }
        # when
        result = tab_status_indicator(
            context, Character.UpdateSection.LOCATION, Character.UpdateSection.MAILS
        )
        # then
        self.assertEqual(result["tab_update_status"], Character.TotalUpdateStatus.ERROR)

    def test_should_not_report_error_when_all_sections_ok(self):
        # given
        status_location = CharacterUpdateStatus(
            section=Character.UpdateSection.LOCATION, is_success=True
        )
        status_mails = CharacterUpdateStatus(
            section=Character.UpdateSection.LOCATION, is_success=True
        )
        sections_update_status = {"location": status_location, "mails": status_mails}
        context = {
            "sections_update_status": sections_update_status,
            "total_update_status": Character.TotalUpdateStatus.OK,
        }
        # when
        result = tab_status_indicator(
            context, Character.UpdateSection.LOCATION, Character.UpdateSection.MAILS
        )
        # then
        self.assertEqual(result["tab_update_status"], Character.TotalUpdateStatus.OK)

    def test_should_break_when_section_is_invalid(self):
        # given
        status_location = CharacterUpdateStatus(
            section=Character.UpdateSection.LOCATION, is_success=True
        )
        sections_update_status = {"location": status_location}
        context = {
            "sections_update_status": sections_update_status,
            "total_update_status": Character.TotalUpdateStatus.OK,
        }
        # when/then
        with self.assertRaises(ValueError):
            tab_status_indicator(context, "invalid-section-name")

    def test_should_not_report_error_when_status_is_disabled(self):
        # given
        status = CharacterUpdateStatus(
            section=Character.UpdateSection.LOCATION, is_success=False
        )
        sections_update_status = {"location": status}
        context = {
            "sections_update_status": sections_update_status,
            "total_update_status": Character.TotalUpdateStatus.DISABLED,
        }
        # when
        result = tab_status_indicator(context, Character.UpdateSection.LOCATION)
        # then
        self.assertEqual(result["tab_update_status"], Character.TotalUpdateStatus.OK)

    def test_should_report_incomplete_when_one_of_several_sections_is_missing(self):
        # given
        status_location = CharacterUpdateStatus(
            section=Character.UpdateSection.LOCATION, is_success=True
        )
        sections_update_status = {"location": status_location}
        context = {
            "sections_update_status": sections_update_status,
            "total_update_status": Character.TotalUpdateStatus.INCOMPLETE,
        }
        # when
        result = tab_status_indicator(
            context, Character.UpdateSection.LOCATION, Character.UpdateSection.MAILS
        )
        # then
        self.assertEqual(
            result["tab_update_status"], Character.TotalUpdateStatus.INCOMPLETE
        )

    def test_should_ignore_sections_in_progress(self):
        # given
        status_location = CharacterUpdateStatus(
            section=Character.UpdateSection.LOCATION, is_success=True
        )
        status_mails = CharacterUpdateStatus(
            section=Character.UpdateSection.LOCATION, is_success=None
        )
        sections_update_status = {"location": status_location, "mails": status_mails}
        context = {
            "sections_update_status": sections_update_status,
            "total_update_status": Character.TotalUpdateStatus.ERROR,
        }
        # when
        result = tab_status_indicator(
            context, Character.UpdateSection.LOCATION, Character.UpdateSection.MAILS
        )
        # then
        self.assertEqual(result["tab_update_status"], Character.TotalUpdateStatus.OK)
