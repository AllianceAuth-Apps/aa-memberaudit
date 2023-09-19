"""Eve Online fittings."""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Union

from eveuniverse.models import EveType

from .skills import Skill, compress_skills, required_skills_from_eve_types


@dataclass(frozen=True)
class _BaseFittingItem:
    def eve_types(self) -> Set[EveType]:
        """Return types used in this fitting."""
        raise NotImplementedError()

    @property
    def is_empty(self) -> bool:
        """Return True if fitting empty, else False."""
        raise NotImplementedError()

    def to_eft(self) -> str:
        """Convert to EFT string format."""
        raise NotImplementedError()

    def __init__(self) -> None:
        raise RuntimeError("No instantiation from abstract base class")


@dataclass(frozen=True)
class Module(_BaseFittingItem):
    """A ship module used in a fitting."""

    module_type: Optional[EveType] = None
    charge_type: Optional[EveType] = None
    is_offline: bool = False

    @property
    def is_empty(self) -> bool:
        return self.module_type is None

    def eve_types(self) -> Union[Set[EveType], set]:
        """Eve types used in this module."""
        types = set()
        if self.module_type:
            types.add(self.module_type)
        if self.charge_type:
            types.add(self.charge_type)
        return types

    def to_eft(self) -> str:
        """Convert to EFT format."""
        if not self.module_type:
            raise ValueError("Module is empty")
        text = self.module_type.name
        if self.charge_type:
            text += f", {self.charge_type.name}"
        if self.is_offline:
            text += " /OFFLINE"
        return text


@dataclass(frozen=True)
class Item(_BaseFittingItem):
    """An item used in a fitting."""

    item_type: EveType
    quantity: Optional[int] = None

    @property
    def is_empty(self) -> bool:
        return False

    def eve_types(self) -> Set[EveType]:
        """Eve types used in this item."""
        return {self.item_type}

    def to_eft(self) -> str:
        """Convert to EFT format."""
        text = self.item_type.name
        if self.quantity:
            text += f" x{self.quantity}"
        return text


@dataclass(frozen=True)
class Fitting:
    """A fitting for a ship in Eve Online."""

    name: str
    ship_type: EveType
    high_slots: List[Module] = field(default_factory=list)
    medium_slots: List[Module] = field(default_factory=list)
    low_slots: List[Module] = field(default_factory=list)
    rig_slots: List[Module] = field(default_factory=list)
    subsystem_slots: List[Module] = field(default_factory=list)
    drone_bay: List[Item] = field(default_factory=list)
    fighter_bay: List[Item] = field(default_factory=list)
    implants: List[Item] = field(default_factory=list)
    boosters: List[Item] = field(default_factory=list)
    cargo_bay: List[Item] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.name}"

    @property
    def modules(self) -> List[Module]:
        """All fitted modules."""
        return (
            self.high_slots
            + self.medium_slots
            + self.low_slots
            + self.rig_slots
            + self.subsystem_slots
        )

    def eve_types(self) -> Set[EveType]:
        """Types of all modules and items."""
        objs = (
            self.modules
            + self.drone_bay
            + self.fighter_bay
            + self.implants
            + self.boosters
            + self.cargo_bay
        )
        types = {self.ship_type}
        for obj in [o for o in objs if o]:
            types |= obj.eve_types()
        return types

    def required_skills(self) -> List[Skill]:
        """Skills required to fly this fitting."""
        eve_types = self.eve_types()
        skills = required_skills_from_eve_types(eve_types)
        return compress_skills(skills)

    def to_eft(self) -> str:
        """Return this fitting in EFT format."""

        def add_section(objs, keyword: Optional[str] = None) -> List[str]:
            lines = [""]
            for obj in objs:
                lines.append(
                    obj.to_eft() if not obj.is_empty else f"[Empty {keyword} slot]"
                )
            return lines

        lines = []
        lines.append(f"[{self.ship_type.name}, {self.name}]")
        lines += add_section(self.low_slots, "Low")
        lines += add_section(self.medium_slots, "Med")
        lines += add_section(self.high_slots, "High")
        lines += add_section(self.rig_slots, "Rig")
        if self.subsystem_slots:
            lines += add_section(self.subsystem_slots, "Subsystem")
        if self.drone_bay:
            lines.append("")
            lines += add_section(self.drone_bay)
        if self.fighter_bay:
            lines.append("")
            lines += add_section(self.fighter_bay)
        if self.implants:
            lines.append("")
            lines += add_section(self.implants)
        if self.boosters:
            lines.append("")
            lines += add_section(self.boosters)
        if self.cargo_bay:
            lines.append("")
            lines += add_section(self.cargo_bay)
        return "\n".join(lines)
