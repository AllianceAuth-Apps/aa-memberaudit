"""Create testdata for eveuniverse models by fetching them from ESI."""

from django.test import TestCase
from eveuniverse.models import EveUniverseEntityModel
from eveuniverse.tools.testdata import ModelSpec, create_testdata

from memberaudit.constants import EveCategoryId

from . import eveuniverse_test_data_filename


class CreateEveUniverseTestData(TestCase):
    def test_create_testdata(self):
        testdata_spec = [
            ModelSpec("EveAncestry", ids=[11]),
            ModelSpec("EveBloodline", ids=[1]),
            ModelSpec("EveFaction", ids=[500001]),
            ModelSpec("EveRace", ids=[1]),
            ModelSpec("EvePlanet", ids=[40161463, 40161464, 40161467, 40161469]),
            ModelSpec(
                "EveSolarSystem", ids=[30000142, 30004984, 30001161, 30002537, 30000380]
            ),
            ModelSpec(
                "EveCategory", ids=[EveCategoryId.ASTEROID.value], include_children=True
            ),
            ModelSpec(
                "EveType",
                ids=[
                    2,
                    5,
                    23,
                    60,
                    603,
                    670,
                    1376,
                    16159,
                    20185,
                    24311,
                    24312,
                    24313,
                    24314,
                    35832,
                    35835,
                    52678,
                ],
            ),
            ModelSpec(
                "EveType",
                ids=[
                    519,  # Gyrostabilizer II
                    2048,  # Damage Control II
                    1999,  # Tracking Enhancer II
                    1952,  # Sensor Booster II
                    3244,  # Warp Disruptor II
                    5973,  # 5MN Y-T8 Compact Microwarpdrive
                    2977,  # 280mm Howitzer Artillery II
                    21924,  # Republic Fleet Phased Plasma S
                    31328,  # Small Targeting System Subcontroller II
                    31740,  # Small Thermal Shield Reinforcer I
                    31752,  # Small Kinetic Shield Reinforcer I
                    34562,  # Svipul
                    19540,  # High-grade Snake Alpha
                    19551,  # High-grade Snake Beta
                    19553,  # High-grade Snake Gamma
                    4405,
                    23757,
                    15729,
                    16273,
                    21096,
                    23059,
                    24283,
                    24395,
                    28999,
                    29001,
                    29009,
                    30993,
                    31013,
                    31025,
                    31942,
                    40351,
                    41155,
                    41411,
                    41489,
                    41491,
                    185,
                    31716,
                    31177,
                    31370,
                    3244,
                    2605,
                    593,
                    8433,
                    5971,
                    4405,
                    2488,
                    2873,
                    2205,
                    3328,
                    3425,
                    3394,
                    3300,
                    12485,
                    3302,
                    12484,
                    3435,
                    3436,
                    11084,
                    24241,
                    3318,
                    3454,
                    3436,
                    12484,
                    24241,
                    45999,
                    2048,
                    2281,
                    2301,
                    3082,
                    3841,
                    10190,
                    12058,
                    12805,
                    29984,
                    31796,
                    45626,  # TENGU start
                    45590,
                    45602,
                    45615,
                    30544,
                    30552,
                    30651,
                    30548,
                    30549,
                    3335,  # Amarr Cruiser skill
                    52797,  # 2nd "Amarr Cruiser" skill
                ],
                enabled_sections=[EveUniverseEntityModel.LOAD_DOGMAS],
            ),
        ]
        create_testdata(testdata_spec, eveuniverse_test_data_filename())
