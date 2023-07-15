"""Member Audit forms."""

from django import forms
from django.core.exceptions import ValidationError

from memberaudit.core.eft_parser import EftParserError, create_fitting_from_eft
from memberaudit.core.skill_plans import SkillPlan, SkillPlanError
from memberaudit.models import SkillSet, SkillSetGroup
from memberaudit.models.constants import NAMES_MAX_LENGTH


class ImportFittingForm(forms.Form):
    """Form for importing an EFT fitting."""

    fitting_text = forms.CharField(
        label="",
        widget=forms.Textarea(
            attrs={
                "placeholder": "Paste fitting in EFT format into this field...",
                "rows": 30,
                "cols": 100,
            }
        ),
    )
    can_overwrite = forms.BooleanField(
        label="Overwrite skill sets with same name", required=False
    )
    skill_set_name = forms.CharField(
        label="New Name",
        max_length=NAMES_MAX_LENGTH,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Instead of name from fitting."}),
    )
    skill_set_group = forms.ModelChoiceField(
        label="Add to skill set group",
        required=False,
        queryset=SkillSetGroup.objects.order_by("name"),
    )

    def clean(self):
        data = super().clean()
        try:
            fitting, errors = create_fitting_from_eft(data["fitting_text"])
        except EftParserError:
            raise ValidationError(
                {
                    "fitting_text": (
                        "This fitting does not appear to be a valid EFT format."
                    )
                }
            ) from None

        data["_fitting"] = fitting
        data["_errors"] = errors
        skill_set_name = data.get("skill_set_name") or fitting.name
        if (
            not data["can_overwrite"]
            and SkillSet.objects.filter(name=skill_set_name).exists()
        ):
            raise ValidationError(
                f"A skill set with the name '{skill_set_name}' already exists."
            )
        data["_skill_set_name"] = skill_set_name
        return data


class ImportSkillPlanForm(forms.Form):
    """Form for importing a skill plan."""

    skill_plan_text = forms.CharField(
        label="",
        widget=forms.Textarea(
            attrs={
                "placeholder": "Paste skill plan from Eve Online or Eve Mon into this field...",
                "rows": 30,
                "cols": 100,
            }
        ),
    )
    skill_set_name = forms.CharField(
        label="Name",
        max_length=NAMES_MAX_LENGTH,
        widget=forms.TextInput(attrs={"placeholder": "Name of the new skill set"}),
    )
    can_overwrite = forms.BooleanField(
        label="Overwrite skill sets with same name", required=False
    )
    skill_set_group = forms.ModelChoiceField(
        label="Add to skill set group",
        required=False,
        queryset=SkillSetGroup.objects.order_by("name"),
    )

    def clean(self):
        data = super().clean()
        try:
            skill_plan, errors = SkillPlan.create_from_plain_text(
                name=data["skill_set_name"], text=data["skill_plan_text"]
            )
        except SkillPlanError:
            raise ValidationError(
                {"skill_plan_text": "This does not appear to be a valid skill plan."}
            ) from None

        data["_skill_plan"] = skill_plan
        data["_errors"] = errors
        if (
            not data["can_overwrite"]
            and SkillSet.objects.filter(name=data["skill_set_name"]).exists()
        ):
            raise ValidationError(
                {"skill_set_name": "A skill set with this name already exists."}
            )
        return data
