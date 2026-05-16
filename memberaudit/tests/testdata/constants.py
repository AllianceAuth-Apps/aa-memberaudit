from enum import IntEnum


class EveCategoryId(IntEnum):
    """Eve Online named category IDs"""

    ABSTRACT = 29
    ASTEROID = 25
    BLUEPRINT = 9
    CELESTIAL = 2
    CHARGE = 8
    DRONE = 18
    FIGHTER = 87
    IMPLANT = 20
    MODULE = 7
    SHIP = 6
    SKILL = 16
    STATION = 3
    STRUCTURE = 65
    SUBSYSTEM = 32


class EveDogmaAttributeId(IntEnum):
    """Eve Online named dogma attribute IDs"""

    IMPLANT_SLOT = 331


class EveFactionId(IntEnum):
    CALDARI_STATE = 500_001


class EveGroupId(IntEnum):
    """Eve Online named group IDs"""

    CAPSULE = 29
    CYBERIMPLANT = 300
    MISCELLANEOUS = 1319
    NAVIGATION = 275
    SOLAR_SYSTEM = 5
    SPACESHIP_COMMAND = 257


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
