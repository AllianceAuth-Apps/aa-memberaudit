"""Eve Online Skills."""

from collections import defaultdict
from dataclasses import dataclass
from typing import DefaultDict, Dict, Iterable, List, Tuple

from eveuniverse.models import EveType, EveTypeDogmaAttribute

from memberaudit.constants import EveDogmaAttributeId as AttributeId
from memberaudit.helpers import arabic_number_to_roman


@dataclass(frozen=True)
class Skill:
    """A skill in Eve Online."""

    eve_type: EveType
    level: int

    def __str__(self) -> str:
        level_str = arabic_number_to_roman(self.level)
        return f"{self.eve_type.name} {level_str}"

    def __lt__(self, other):
        if self.eve_type != other.eve_type:
            raise ValueError("'<' not supported for skills of different type")
        return self.level < other.level

    def __le__(self, other):
        if self.eve_type != other.eve_type:
            raise ValueError("'<=' not supported for skills of different type")
        return self.level <= other.level

    def __gt__(self, other):
        if self.eve_type != other.eve_type:
            raise ValueError("'>' not supported for skills of different type")
        return self.level > other.level

    def __ge__(self, other):
        if self.eve_type != other.eve_type:
            raise ValueError("'>=' not supported for skills of different type")
        return self.level >= other.level


def compress_skills(skills: List["Skill"]) -> List["Skill"]:
    """Compresses a list of skill by removing redundant skills."""
    skills_map = defaultdict(list)
    for skill in skills:
        skills_map[skill.eve_type.id].append(skill)
    return [max(same_skills) for _, same_skills in skills_map.items()]


def required_skills_from_eve_types(
    eve_types: Iterable[EveType],
) -> List["Skill"]:
    """Create list of required skills from eve types.

    For best performance make sure that all types have been loaded with dogmas.
    """
    skills_raw = _identify_skills_from_eve_types(eve_types)
    skill_types = _gather_skill_types(skills_raw)
    skills = [
        Skill(eve_type=skill_types[type_id], level=level)
        for type_id, level in skills_raw
    ]
    return sorted(skills, key=lambda o: o.eve_type.name)


def _identify_skills_from_eve_types(
    eve_types: Iterable[EveType],
) -> List[Tuple[int, int]]:
    eve_types = _reload_eve_types_without_dogmas(eve_types)
    all_attributes_map = _fetch_attributes_for_eve_types(eve_types)
    return _create_skills_from_attributes(all_attributes_map)


def _reload_eve_types_without_dogmas(eve_types: Iterable[EveType]) -> Iterable[EveType]:
    for eve_type in eve_types:
        if not eve_type.enabled_sections.dogmas:
            eve_type, _ = EveType.objects.update_or_create_esi(
                id=eve_type.id, enabled_sections=[EveType.Section.DOGMAS]
            )
    return eve_types


def _fetch_attributes_for_eve_types(
    eve_types: Iterable[EveType],
) -> Dict[int, Dict[int, int]]:
    eve_type_ids = {obj.id for obj in eve_types}
    all_attributes_raw = EveTypeDogmaAttribute.objects.filter(
        eve_dogma_attribute_id__in=[
            AttributeId.REQUIRED_SKILL_1,
            AttributeId.REQUIRED_SKILL_1_LEVEL,
            AttributeId.REQUIRED_SKILL_2,
            AttributeId.REQUIRED_SKILL_2_LEVEL,
            AttributeId.REQUIRED_SKILL_3,
            AttributeId.REQUIRED_SKILL_3_LEVEL,
            AttributeId.REQUIRED_SKILL_4,
            AttributeId.REQUIRED_SKILL_4_LEVEL,
            AttributeId.REQUIRED_SKILL_5,
            AttributeId.REQUIRED_SKILL_5_LEVEL,
            AttributeId.REQUIRED_SKILL_6,
            AttributeId.REQUIRED_SKILL_6_LEVEL,
        ],
        eve_type_id__in=eve_type_ids,
    ).values_list("eve_type_id", "eve_dogma_attribute_id", "value")
    all_attributes_map: DefaultDict[int, Dict[int, int]]
    all_attributes_map = defaultdict(dict)
    for eve_type_id, eve_dogma_attribute_id, value in all_attributes_raw:
        all_attributes_map[eve_type_id][eve_dogma_attribute_id] = int(value)
    return all_attributes_map


def _create_skills_from_attributes(
    all_attributes_map: Dict[int, Dict[int, int]]
) -> List[Tuple[int, int]]:
    skills = []
    for attributes in all_attributes_map.values():
        for skill_id, skill_level_id in {
            AttributeId.REQUIRED_SKILL_1: AttributeId.REQUIRED_SKILL_1_LEVEL,
            AttributeId.REQUIRED_SKILL_2: AttributeId.REQUIRED_SKILL_2_LEVEL,
            AttributeId.REQUIRED_SKILL_3: AttributeId.REQUIRED_SKILL_3_LEVEL,
            AttributeId.REQUIRED_SKILL_4: AttributeId.REQUIRED_SKILL_4_LEVEL,
            AttributeId.REQUIRED_SKILL_5: AttributeId.REQUIRED_SKILL_5_LEVEL,
            AttributeId.REQUIRED_SKILL_6: AttributeId.REQUIRED_SKILL_6_LEVEL,
        }.items():
            if skill_id in attributes and skill_level_id in attributes:
                skills.append((attributes[skill_id], attributes[skill_level_id]))
    return skills


def _gather_skill_types(skills_raw: List[Tuple[int, int]]) -> Dict[int, EveType]:
    type_ids = {skill[0] for skill in skills_raw}
    skill_types = {obj.id: obj for obj in EveType.objects.filter(id__in=type_ids)}
    missing_type_ids = type_ids - set(skill_types.keys())
    for type_id in missing_type_ids:
        eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
        skill_types[type_id] = eve_type
    return skill_types
