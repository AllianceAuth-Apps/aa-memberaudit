from enum import IntEnum


class EveCategoryId(IntEnum):
    """Eve Online named category IDs"""

    ASTEROID = 25
    BLUEPRINT = 9
    CHARGE = 8
    DRONE = 18
    FIGHTER = 87
    IMPLANT = 20
    MODULE = 7
    SKILL = 16
    SUBSYSTEM = 32
    STATION = 3
    SHIP = 6
    STRUCTURE = 65


class EveFactionId(IntEnum):
    CALDARI_STATE = 500_001


class EveSolarSystemId(IntEnum):
    """Eve Online named type IDs"""

    AMAMAKE = 30002537
    HED_GP = 30001161
    JITA = 30000142
    POLARIS = 30000380


class EveStationId(IntEnum):
    """Eve Online named station IDs"""

    JITA_44 = 60003760


class EveTypeId(IntEnum):
    """Eve Online named type IDs"""

    AMARR_CARRIER = 24311  # skill
    ASSET_SAFETY_WRAP = 60
    ASTRAHUS = 35832  # structure
    CALDARI_CARRIER = 24312  # skill
    CAPSULE = 670  # ship
    CARGO_CONTAINER = 23
    CHARON = 20185  # ship
    HIGH_GRADE_SNAKE_ALPHA = 19540  # implant
    LIQUID_OZONE = 16273
    MERLIN = 603  # ship
    SOLAR_SYSTEM = 5
    VELDSPAR = 1230
