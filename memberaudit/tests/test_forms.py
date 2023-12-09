from eveuniverse.models import EveType

from app_utils.testing import NoSocketsTestCase

from memberaudit import forms
from memberaudit.core.fittings import Fitting

from .testdata.factories import (
    create_fitting_text,
    create_skill,
    create_skill_plan,
    create_skill_set,
)
from .testdata.load_eveuniverse import load_eveuniverse


class TestImportFittingForm(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()
        cls.fitting_text = create_fitting_text("fitting_tristan.txt")

    def test_should_raise_no_errors(self):
        # given
        form = forms.ImportFittingForm(data={"fitting_text": self.fitting_text})
        # when
        self.assertTrue(form.is_valid())
        self.assertIsInstance(form.cleaned_data["_fitting"], Fitting)
        self.assertListEqual(form.cleaned_data["_errors"], [])

    def test_should_raise_error_when_fitting_text_is_invalid(self):
        # given
        form = forms.ImportFittingForm(data={"fitting_text": "invalid"})
        # when
        self.assertFalse(form.is_valid())
        self.assertIn("fitting_text", form.errors.keys())

    def test_should_raise_error_when_skill_set_already_exists_1(self):
        # given
        create_skill_set(name="Tristan - Standard Kite (cap stable)")
        form = forms.ImportFittingForm(data={"fitting_text": self.fitting_text})
        # when
        self.assertFalse(form.is_valid())

    def test_should_raise_error_when_skill_set_already_exists_2(self):
        # given
        create_skill_set(name="My name")
        form = forms.ImportFittingForm(
            data={"fitting_text": self.fitting_text, "skill_set_name": "My name"}
        )
        # when
        self.assertFalse(form.is_valid())


class TestImportSkillPlanForm(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_raise_no_errors(self):
        # given
        form = forms.ImportSkillPlanForm(
            data={
                "skill_plan_text": "Caldari Core Systems 5",
                "skill_set_name": "My name",
            }
        )
        # when
        self.assertTrue(form.is_valid())
        expected_skill_plan = create_skill_plan(
            name="My name",
            skills=[
                create_skill(
                    eve_type=EveType.objects.get(name="Caldari Core Systems"), level=5
                )
            ],
        )
        self.assertEqual(form.cleaned_data["_skill_plan"], expected_skill_plan)
        self.assertListEqual(form.cleaned_data["_errors"], [])

    def test_should_raise_error_when_skill_set_already_exists(self):
        # given
        create_skill_set(name="My name")
        form = forms.ImportSkillPlanForm(
            data={
                "skill_plan_text": "Caldari Core Systems 5",
                "skill_set_name": "My name",
            }
        )
        # when
        self.assertFalse(form.is_valid())
        self.assertIn("skill_set_name", form.errors.keys())

    def test_should_raise_error_when_skill_plan_invalid(self):
        # given
        create_skill_set(name="My name")
        form = forms.ImportSkillPlanForm(
            data={
                "skill_plan_text": "Invalid skill plan",
                "skill_set_name": "My name",
            }
        )
        # when
        self.assertFalse(form.is_valid())
        self.assertIn("skill_plan_text", form.errors.keys())
