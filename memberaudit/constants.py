"""Shared constants for Member Audit."""

import sys
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
    """Eve Online named faction IDs"""

    AMARR_EMPIRE = 500_003
    CALDARI_STATE = 500_001
    GALLENTE_FEDERATION = 500_004
    MINMATAR_REPUBLIC = 500_002


class EveGroupId(IntEnum):
    """Eve Online named group IDs"""

    CAPSULE = 29
    CYBERIMPLANT = 300
    BOOSTER = 303


class EveSolarSystemId(IntEnum):
    """Eve Online solar system IDs."""

    POLARIS = 30000380


class EveTypeId(IntEnum):
    """Eve Online named type IDs"""

    ASSET_SAFETY_WRAP = 60
    SOLAR_SYSTEM = 5


class EveSkillTypeId(IntEnum):
    """Eve Online named skill type IDs"""

    CONNECTIONS = 3359
    CRIMINAL_CONNECTIONS = 3361
    DIPLOMACY = 3357


class EveDogmaAttributeId(IntEnum):
    """Eve Online named dogma attribute IDs"""

    IMPLANT_SLOT = 331
    REQUIRED_SKILL_1 = 182
    REQUIRED_SKILL_1_LEVEL = 277
    REQUIRED_SKILL_2 = 183
    REQUIRED_SKILL_2_LEVEL = 278
    REQUIRED_SKILL_3 = 184
    REQUIRED_SKILL_3_LEVEL = 279
    REQUIRED_SKILL_4 = 1285
    REQUIRED_SKILL_4_LEVEL = 1286
    REQUIRED_SKILL_5 = 1289
    REQUIRED_SKILL_5_LEVEL = 1287
    REQUIRED_SKILL_6 = 1290
    REQUIRED_SKILL_6_LEVEL = 1288


class EveDogmaEffectId(IntEnum):
    """Eve Online named dogma effect IDs"""

    LO_POWER = 11
    HI_POWER = 12
    MED_POWER = 13
    RIG_SLOT = 2663
    SUB_SYSTEM = 3772


DATETIME_FORMAT = "%Y-%b-%d %H:%M"
MY_DATETIME_FORMAT = "Y-M-d H:i"
DEFAULT_ICON_SIZE = 32
SKILL_SET_DEFAULT_ICON_TYPE_ID = 3327
MAIL_LABEL_ID_ALL_MAILS = 0

IS_TESTING = sys.argv[1:2] == ["test"]
"""True when tests are currently running, else False."""
