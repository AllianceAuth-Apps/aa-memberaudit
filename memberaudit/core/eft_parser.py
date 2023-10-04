"""Parser for fitting in EFT Format"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from bravado.exception import HTTPNotFound

from eveuniverse.models import EveEntity, EveType

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__
from memberaudit.constants import EveCategoryId, EveDogmaEffectId, EveGroupId

from .fittings import Fitting, Item, Module

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


class EftParserError(Exception):
    """Base error for EFT parser."""


class UnknownShipTypeError(EftParserError):
    """Ship type is unknown."""


class MissingTitleError(EftParserError):
    """Title is missing."""


class MissingSectionsError(EftParserError):
    """Insufficient sections defined."""


@dataclass
class _EveTypes:
    """Container with EveType objects to enable quick name to object resolution."""

    objs_by_name: Dict[str, EveType] = field(default_factory=dict)

    def from_name(self, type_name: Optional[str]) -> Optional[EveType]:
        """Resolve given type name into EveType object.

        Returns ``None`` if it can not be resolved.
        """
        if type_name is None:
            return None
        return self.objs_by_name.get(str(type_name))

    @classmethod
    def create_from_names(
        cls, type_names: Iterable[str]
    ) -> Tuple["_EveTypes", Set[str]]:
        """Create new object from list of type names.

        Will try to fetch types from DB first and load missing types from ESI.
        All types must have dogmas.

        Returns:
            created object, list of type names that could not be resolved
        """
        if not isinstance(type_names, (set, list, tuple)):
            raise TypeError("type_name must be of type list, set or tuple.")
        type_names = set(type_names)
        eve_types = cls._fetch_types_from_db(type_names)
        missing_type_names = type_names - set(eve_types.keys())
        if missing_type_names:
            added_eve_types, missing_type_names_2 = cls._fetch_missing_types_from_esi(
                missing_type_names
            )
            eve_types.update(added_eve_types)
        else:
            missing_type_names_2 = set()
        return cls(eve_types), missing_type_names_2

    @classmethod
    def _fetch_types_from_db(cls, type_names: Iterable[str]) -> Dict[str, EveType]:
        eve_types_query = (
            EveType.objects.select_related("eve_group")
            .prefetch_related("dogma_effects")
            .filter(
                enabled_sections=EveType.enabled_sections.dogmas, name__in=type_names  # type: ignore
            )
        )
        eve_types = {obj.name: obj for obj in eve_types_query}
        return eve_types

    @classmethod
    def _fetch_missing_types_from_esi(
        cls,
        missing_type_names: Set[str],
    ) -> Tuple[Dict[str, EveType], Set[str]]:
        def type_names_str(type_names: Iterable) -> str:
            return ", ".join(sorted(list(type_names)))

        logger.info(
            "EFT parser: trying to fetch unknown types from ESI: %s",
            type_names_str(missing_type_names),
        )
        entity_ids = (
            EveEntity.objects.fetch_by_names_esi(missing_type_names)
            .filter(category=EveEntity.CATEGORY_INVENTORY_TYPE)
            .values_list("id", flat=True)
        )
        eve_types = cls._fetch_types_from_esi(entity_ids)
        missing_type_names_2 = missing_type_names - set(eve_types.keys())
        if missing_type_names_2:
            logger.info(
                "EFT parser: failed to identify types: %s",
                type_names_str(missing_type_names_2),
            )
        return eve_types, missing_type_names_2

    @staticmethod
    def _fetch_types_from_esi(entity_ids) -> Dict[str, EveType]:
        eve_types = {}
        for entity_id in entity_ids:
            try:
                obj, _ = EveType.objects.get_or_create_esi(
                    id=entity_id, enabled_sections=[EveType.Section.DOGMAS]
                )
            except HTTPNotFound:
                pass
            else:
                eve_types[obj.name] = obj  # type: ignore
        return eve_types

    # @classmethod
    # def _fetch_types_from_esi(cls, entity_ids) -> Dict[str, EveType]:
    #     """Fetch types from ESI concurrently using threads."""
    #     max_workers = getattr(settings, "ESI_CONNECTION_POOL_MAXSIZE", 10)
    #     with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    #         eve_types = executor.map(cls._fetch_type_from_esi, entity_ids)
    #     return {obj.name: obj for obj in eve_types if obj}

    # @staticmethod
    # def _fetch_type_from_esi(entity_id) -> Optional[EveType]:
    #     """Fetch type from ESI."""
    #     try:
    #         obj, _ = EveType.objects.get_or_create_esi(
    #             id=entity_id, enabled_sections=[EveType.Section.DOGMAS]
    #         )
    #     except HTTPNotFound:
    #         return None
    #     else:
    #         return obj


class _EftSlotType(Enum):
    """An EFT slot type."""

    NONE = auto()
    LOW_SLOT = auto()
    MEDIUM_SLOT = auto()
    HIGH_SLOT = auto()
    RIG_SLOT = auto()
    SUBSYSTEM_SLOT = auto()


@dataclass
class _EftTextItem:
    """Text item of an EFT fitting used for parsing."""

    item_type: Optional[str] = None
    charge_type: Optional[str] = None
    quantity: Optional[int] = None
    is_offline: bool = False
    slot_type: _EftSlotType = _EftSlotType.NONE

    def type_names(self) -> Set[str]:
        """Return types used in the item."""
        types = set()
        if self.item_type:
            types.add(self.item_type)
        if self.charge_type:
            types.add(self.charge_type)
        return types

    @classmethod
    def create_from_line(cls, line: str) -> "_EftTextItem":
        """Create new object from text line."""
        empty_line_parsed = line.strip("[]").lower()
        if "empty " in empty_line_parsed:
            if " high " in empty_line_parsed:
                return cls(slot_type=_EftSlotType.HIGH_SLOT)
            if " med " in empty_line_parsed:
                return cls(slot_type=_EftSlotType.MEDIUM_SLOT)
            if " low " in empty_line_parsed:
                return cls(slot_type=_EftSlotType.LOW_SLOT)
            if " rig " in empty_line_parsed:
                return cls(slot_type=_EftSlotType.RIG_SLOT)
            if " subsystem " in empty_line_parsed:
                return cls(slot_type=_EftSlotType.SUBSYSTEM_SLOT)
            return cls()
        part = line.split()[-1]
        if "x" in part and part[1:].isdigit():
            item_type = line.split(part)[0].strip()
            quantity = part[1:]
            return cls(item_type=item_type, quantity=int(quantity))
        if "/OFFLINE" in line:
            is_offline = True
            line = line.replace(" /OFFLINE", "")
        else:
            is_offline = False
        if "," in line:
            item_type, charge_type = line.split(",")
            charge_type = charge_type.strip()
            return cls(
                item_type=item_type, charge_type=charge_type, is_offline=is_offline
            )
        return cls(item_type=line.strip(), is_offline=is_offline)


@dataclass
class _EftTextSection:
    """Text section of an EFT fitting used for parsing."""

    items: List[_EftTextItem] = field(default_factory=list)

    def type_names(self) -> Set[str]:
        """Return types used in the section."""
        types = set()
        for item in self.items:
            types |= item.type_names()
        return types

    @classmethod
    def create_from_lines(cls, lines: Iterable[str]) -> "_EftTextSection":
        """Create new object from lines."""
        items = [_EftTextItem.create_from_line(line) for line in lines]
        return cls(items=items)


@dataclass
class _EftItem:
    """Item of an EFT fitting used for parsing."""

    item_type: Optional[EveType] = None
    charge_type: Optional[EveType] = None
    quantity: Optional[int] = None
    is_offline: bool = False
    slot_type: _EftSlotType = _EftSlotType.NONE

    @property
    def is_empty(self) -> bool:
        """Return True if this item is empty, else False."""
        return self.item_type is None

    @property
    def is_slot(self) -> bool:
        """Return True if this item is a slot, else False."""
        return self.quantity is None

    def is_booster(self) -> bool:
        """Return True if this item is a booster, else False."""
        if self.is_empty:
            return False
        return self._item_group_id() == EveGroupId.BOOSTER

    def is_cyber_implant(self) -> bool:
        """Return True if this item is a cyber slot, else False."""
        if self.is_empty:
            return False
        return self._item_group_id() == EveGroupId.CYBERIMPLANT

    def is_drone(self) -> bool:
        """Return True if this item is a drone, else False."""
        if self.is_empty:
            return False
        return self._item_category_id() == EveCategoryId.DRONE

    def is_fighter(self) -> bool:
        """Return True if this item is a fighter, else False."""
        if self.is_empty:
            return False
        return self._item_category_id() == EveCategoryId.FIGHTER

    def is_high_slot(self) -> bool:
        """Return True if this item is a high slot, else False."""
        if self.slot_type is _EftSlotType.HIGH_SLOT:
            return True

        if self.is_empty:
            return False

        effect_ids = {
            obj.eve_dogma_effect_id for obj in self.item_type.dogma_effects.all()
        }
        return EveDogmaEffectId.HI_POWER in effect_ids

    def is_med_slot(self) -> bool:
        """Return True if this item is a med slot, else False."""
        if self.slot_type is _EftSlotType.MEDIUM_SLOT:
            return True

        if self.is_empty:
            return False

        effect_ids = {
            obj.eve_dogma_effect_id for obj in self.item_type.dogma_effects.all()
        }
        return EveDogmaEffectId.MED_POWER in effect_ids

    def is_low_slot(self) -> bool:
        """Return True if this item is a low slot, else False."""
        if self.slot_type is _EftSlotType.LOW_SLOT:
            return True

        if self.is_empty:
            return False

        effect_ids = {
            obj.eve_dogma_effect_id for obj in self.item_type.dogma_effects.all()
        }
        return EveDogmaEffectId.LO_POWER in effect_ids

    def is_rig_slot(self) -> bool:
        """Return True if this item is a rig slot."""
        if self.slot_type is _EftSlotType.RIG_SLOT:
            return True

        if self.is_empty:
            return False

        effect_ids = {
            obj.eve_dogma_effect_id for obj in self.item_type.dogma_effects.all()
        }
        return EveDogmaEffectId.RIG_SLOT in effect_ids

    def is_subsystem(self) -> bool:
        """Return True if this item is a subsystem, else False."""
        if self.slot_type is _EftSlotType.SUBSYSTEM_SLOT:
            return True

        if self.is_empty:
            return False

        effect_ids = {
            obj.eve_dogma_effect_id for obj in self.item_type.dogma_effects.all()
        }
        return EveDogmaEffectId.SUB_SYSTEM in effect_ids

    def _item_category_id(self) -> Optional[int]:
        if self.is_empty:
            return None
        return self.item_type.eve_group.eve_category_id

    def _item_group_id(self) -> Optional[int]:
        if self.is_empty:
            return None
        return self.item_type.eve_group_id

    @classmethod
    def create_from_text_item(
        cls, text_item: _EftTextItem, eve_types: _EveTypes
    ) -> "_EftItem":
        """Create new item from text."""
        return cls(
            item_type=eve_types.from_name(text_item.item_type),
            charge_type=eve_types.from_name(text_item.charge_type),
            quantity=text_item.quantity,
            is_offline=text_item.is_offline,
            slot_type=text_item.slot_type,
        )


@dataclass
class _EftSection:
    """Section of an EFT fitting used for parsing."""

    class Category(Enum):
        """A category in an EFT section."""

        UNKNOWN = auto()
        HIGH_SLOTS = auto()
        MEDIUM_SLOTS = auto()
        LOW_SLOTS = auto()
        RIG_SLOTS = auto()
        SUBSYSTEM_SLOTS = auto()
        DRONES_BAY = auto()
        FIGHTER_BAY = auto()
        IMPLANTS = auto()
        BOOSTERS = auto()
        CARGO_BAY = auto()

        @property
        def is_slots(self) -> bool:
            """Return True, if this category has slots."""
            return self in {
                self.HIGH_SLOTS,
                self.MEDIUM_SLOTS,
                self.LOW_SLOTS,
                self.RIG_SLOTS,
            }

    items: List[_EftItem] = field(default_factory=list)
    category: Category = Category.UNKNOWN

    @property
    def is_slots(self) -> bool:
        """Return True if this any item has slots."""
        return any((item.is_slot for item in self.items))

    def guess_category(self) -> Optional["_EftSection.Category"]:
        """Try to guess the category of this section based on it's items.
        Returns ``None`` if the guess fails.
        """
        if self.is_slots:
            if any((item.is_booster() for item in self.items)):
                return self.Category.BOOSTERS
            if any((item.is_cyber_implant() for item in self.items)):
                return self.Category.IMPLANTS
            if any((item.is_low_slot() for item in self.items)):
                return self.Category.LOW_SLOTS
            if any((item.is_med_slot() for item in self.items)):
                return self.Category.MEDIUM_SLOTS
            if any((item.is_high_slot() for item in self.items)):
                return self.Category.HIGH_SLOTS
            if any((item.is_rig_slot() for item in self.items)):
                return self.Category.RIG_SLOTS
            if any((item.is_subsystem() for item in self.items)):
                return self.Category.SUBSYSTEM_SLOTS
        else:
            if any((item.is_drone() for item in self.items)):
                return self.Category.DRONES_BAY
            if any((item.is_fighter() for item in self.items)):
                return self.Category.FIGHTER_BAY
        return None

    def to_modules(self) -> List[Module]:
        """Convert eft items into fitting modules.

        Types from modules that can not be resolved will result in an empty slot.
        """
        objs = []
        for item in self.items:
            if item.is_empty:
                objs.append(Module())
            else:
                params = {"module_type": item.item_type, "is_offline": item.is_offline}
                if item.charge_type:
                    params["charge_type"] = item.charge_type
                objs.append(Module(**params))
        return objs

    def to_items(self) -> List[Item]:
        """Convert eft items into fitting items."""
        objs = []
        for item in self.items:
            params: Dict[str, Any] = {"item_type": item.item_type}
            if item.quantity:
                params["quantity"] = item.quantity
            objs.append(Item(**params))
        return objs

    @classmethod
    def create_from_eft_text_section(
        cls, text_section: _EftTextSection, eve_types: _EveTypes
    ) -> "_EftSection":
        """Create new object from an EFT text section."""
        items = [
            _EftItem.create_from_text_item(item, eve_types)
            for item in text_section.items
        ]
        return cls(items=items)


def create_fitting_from_eft(eft_text: str) -> Tuple[Fitting, List[str]]:
    """Create new object from fitting in EFT format."""
    lines = _text_to_lines(eft_text)
    text_sections = _lines_to_text_sections(lines)
    eft_sections = [
        _EftTextSection.create_from_lines(lines=lines) for lines in text_sections
    ]
    ship_type_name, fitting_name = _parse_title(lines)
    eve_types, unknown_types = _load_eve_types(ship_type_name, eft_sections)
    sections = [
        _EftSection.create_from_eft_text_section(section, eve_types)
        for section in eft_sections
    ]
    sections = _try_to_identify_sections(sections)
    ship_type = eve_types.from_name(ship_type_name)
    if not ship_type:
        raise UnknownShipTypeError(f"Unknown ship type: {ship_type_name}")
    fitting = _create_fitting_from_sections(fitting_name, ship_type, sections)
    errors = _unknown_types_to_errors(unknown_types)
    return fitting, errors


def _text_to_lines(eft_text: str) -> List[str]:
    """Convert text into lines."""
    lines = eft_text.strip().splitlines()
    if not lines:
        raise MissingSectionsError("Text is empty")
    return lines


def _lines_to_text_sections(lines: List[str]) -> List[List[str]]:
    """Split lines into text sections."""
    text_sections = []
    section_lines = []
    for line in lines[1:]:
        if line:
            section_lines.append(line)
        else:
            if section_lines:
                text_sections.append(section_lines)
                section_lines = []
    if section_lines:
        text_sections.append(section_lines)
    return text_sections


def _parse_title(lines: List[str]) -> Tuple[str, str]:
    """Try to parse title from lines."""
    if not lines:
        raise MissingSectionsError("Text is empty")
    line = lines[0]
    if line.startswith("[") and "," in line:
        ship_type_name, fitting_name = line[1:-1].split(",")
        return ship_type_name.strip(), fitting_name.strip()
    raise MissingTitleError("Title not found")


def _load_eve_types(
    ship_type_name: str, sections: List[_EftTextSection]
) -> Tuple["_EveTypes", Set[str]]:
    """Load all EveType objects used in this fitting."""
    type_names = {ship_type_name}
    for section in sections:
        type_names |= section.type_names()
    return _EveTypes.create_from_names(type_names)


def _try_to_identify_sections(sections: List[_EftSection]) -> List[_EftSection]:
    """Identify sections if possible."""
    for section in sections:
        category = section.guess_category()
        if category:
            section.category = category
    # last unknown section must be the cargo bay
    if sections:
        last_section = sections[len(sections) - 1]
        if (
            last_section.category == _EftSection.Category.UNKNOWN
            and not last_section.is_slots
        ):
            last_section.category = _EftSection.Category.CARGO_BAY
    return sections


def _create_fitting_from_sections(
    fitting_name: str, ship_type: EveType, sections: List[_EftSection]
) -> Fitting:
    """Create fitting object from input."""
    params = {"name": fitting_name, "ship_type": ship_type}
    for section in sections:
        if section.category == _EftSection.Category.HIGH_SLOTS:
            params["high_slots"] = section.to_modules()
        elif section.category == _EftSection.Category.MEDIUM_SLOTS:
            params["medium_slots"] = section.to_modules()
        elif section.category == _EftSection.Category.LOW_SLOTS:
            params["low_slots"] = section.to_modules()
        elif section.category == _EftSection.Category.RIG_SLOTS:
            params["rig_slots"] = section.to_modules()
        elif section.category == _EftSection.Category.SUBSYSTEM_SLOTS:
            params["subsystem_slots"] = section.to_modules()
        elif section.category == _EftSection.Category.DRONES_BAY:
            params["drone_bay"] = section.to_items()
        elif section.category == _EftSection.Category.FIGHTER_BAY:
            params["fighter_bay"] = section.to_items()
        elif section.category == _EftSection.Category.IMPLANTS:
            params["implants"] = section.to_items()
        elif section.category == _EftSection.Category.BOOSTERS:
            params["boosters"] = section.to_items()
        elif section.category == _EftSection.Category.CARGO_BAY:
            params["cargo_bay"] = section.to_items()
    return Fitting(**params)


def _unknown_types_to_errors(unknown_types: Set[str]) -> List[str]:
    errors = []
    if unknown_types:
        names = ", ".join(sorted(list(unknown_types)))
        errors.append(f"Ignored modules/items with unknown types: {names}")
    return errors
