from enum import IntEnum


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


class EveTypeId(IntEnum):
    """Eve Online named type IDs"""

    AMARR_CARRIER = 24311  # skill
    ASTRAHUS = 35832
    CALDARI_CARRIER = 24312  # skill
    CAPSULE = 670
    HIGH_GRADE_SNAKE_ALPHA = 19540  # implant
    MERLIN = 603
    SOLAR_SYSTEM = 5
    VELDSPAR = 1230
