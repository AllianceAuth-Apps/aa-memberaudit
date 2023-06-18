"""Eve Online skill plans."""

from dataclasses import dataclass
from typing import List, Tuple

from eveuniverse.models import EveType

from .skills import Skill, compress_skills


class SkillPlanError(Exception):
    """Base error for Skill Plan."""


class NoSkillsIdentified(SkillPlanError):
    """Did not identify any skills."""


@dataclass
class SkillPlan:
    """A skill plan."""

    name: str
    skills: List[Skill]

    @classmethod
    def create_from_plain_text(
        cls, name: str, text: str
    ) -> Tuple["SkillPlan", List[str]]:
        """Create new object from a skill plan in plain text format.

        Can understand Skill names with levels in roman and arabic numbers.
        Empty lines and additional spaces are ignored.

        Args:
            - name: name of the skill plan
            - text: skill plan as multi line string

        Returns:
            - SkillPlan object
            - list of found issues (empty = no issues)

        """
        roman_letter_map = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}
        skills = []
        issues = []
        for line in [obj.strip() for obj in text.splitlines()]:
            if not line:  # ignore empty lines
                continue
            words = line.split(" ")
            skill_level_text = words.pop()
            try:
                skill_level = int(skill_level_text)
            except ValueError:
                skill_level = roman_letter_map.get(skill_level_text)
            if not skill_level:
                issues.append(f"Could not identify skill level. Ignored line: {line}")
                continue
            if skill_level < 1 or skill_level > 5:
                issues.append(f"Invalid skill level. Ignored line: {line}")
                continue
            skill_name = " ".join(words)
            eve_type = EveType.objects.filter(published=True, name=skill_name).first()
            if not eve_type:
                issues.append(f"Could not identify skill. Ignoring line: {line}")
                continue
            skills.append(Skill(eve_type=eve_type, level=skill_level))
        if not skills:
            raise NoSkillsIdentified()
        return cls(name=str(name), skills=compress_skills(skills)), issues
