# from django.test import TestCase

from eveuniverse.models import EveType

from app_utils.testing import NoSocketsTestCase

from ...core.fittings import Fitting, Module, _BaseFittingItem
from ..testdata.factories import create_fitting, create_fitting_text
from ..testdata.load_eveuniverse import load_eveuniverse


class TestBaseFittingItem(NoSocketsTestCase):
    def test_can_not_instantiate(self):
        # given
        with self.assertRaises(RuntimeError):
            _BaseFittingItem()


class TestModule(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()

    def test_should_be_empty(self):
        # given
        module = Module()
        # when/then
        self.assertTrue(module.is_empty)

    def test_should_not_be_empty(self):
        # given
        drones = EveType.objects.get(name="Drone Damage Amplifier II")
        module = Module(module_type=drones)
        # when/then
        self.assertFalse(module.is_empty)

    def test_can_not_convert_empty_module_to_eft(self):
        # given
        module = Module()
        # when/then
        with self.assertRaises(ValueError):
            module.to_eft()

    def test_can_convert_simple_module_to_eft(self):
        # given
        module_type = EveType.objects.get(name="Drone Damage Amplifier II")
        module = Module(module_type=module_type)
        # when
        result = module.to_eft()
        # then
        self.assertEqual(result, "Drone Damage Amplifier II")

    def test_can_convert_module_with_charge_to_eft(self):
        # given
        module_type = EveType.objects.get(name="125mm Gatling AutoCannon II")
        charge_type = EveType.objects.get(name="EMP S")
        module = Module(module_type=module_type, charge_type=charge_type)
        # when
        result = module.to_eft()
        # then
        self.assertEqual(result, "125mm Gatling AutoCannon II, EMP S")

    def test_can_convert_offline_module_to_eft(self):
        # given
        module_type = EveType.objects.get(name="Drone Damage Amplifier II")
        module = Module(module_type=module_type, is_offline=True)
        # when
        result = module.to_eft()
        # then
        self.assertEqual(result, "Drone Damage Amplifier II /OFFLINE")


class TestFitting(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()

    def test_should_return_str(self):
        # given
        ship_type = EveType.objects.get(name="Svipul")
        fitting = Fitting("Dummy Fitting", ship_type)
        # when/then
        self.assertEqual(str(fitting), "Dummy Fitting")

    def test_should_return_eve_types(self):
        # given
        fit = create_fitting()
        # when
        types = fit.eve_types()
        # then
        self.assertSetEqual(
            {obj.id for obj in types}, {185, 31716, 3244, 593, 4405, 2873, 2205}
        )

    def test_eft_parser_roundtrip_archon_normal(self):
        # given
        self.maxDiff = None
        fitting_text_original = create_fitting_text("fitting_archon.txt")
        fitting, _ = Fitting.create_from_eft(fitting_text_original)
        # when
        fitting_text_generated = fitting.to_eft()
        # then
        self.assertEqual(fitting_text_original, fitting_text_generated)

    def test_eft_parser_rountrip_archon_max(self):
        # given
        self.maxDiff = None
        fitting_text_original = create_fitting_text("fitting_archon_max.txt")
        fitting, _ = Fitting.create_from_eft(fitting_text_original)
        # when
        fitting_text_generated = fitting.to_eft()
        # then
        self.assertEqual(fitting_text_original, fitting_text_generated)

    def test_eft_parser_rountrip_tristan(self):
        # given
        self.maxDiff = None
        fitting_text_original = create_fitting_text("fitting_tristan.txt")
        fitting, _ = Fitting.create_from_eft(fitting_text_original)
        # when
        fitting_text_generated = fitting.to_eft()
        # then
        self.assertEqual(fitting_text_original, fitting_text_generated)

    def test_eft_parser_rountrip_svipul_empty_slots_and_offline(self):
        # given
        self.maxDiff = None
        fitting_text_original = create_fitting_text("fitting_svipul_2.txt")
        fitting, _ = Fitting.create_from_eft(fitting_text_original)
        # when
        fitting_text_generated = fitting.to_eft()
        # then
        self.assertEqual(fitting_text_original, fitting_text_generated)

    def test_eft_parser_rountrip_tengu(self):
        # given
        self.maxDiff = None
        fitting_text_original = create_fitting_text("fitting_tengu.txt")
        fitting, _ = Fitting.create_from_eft(fitting_text_original)
        # print(
        #     ", ".join(map(str, sorted(list([obj.id for obj in fitting.eve_types()]))))
        # )
        # when
        fitting_text_generated = fitting.to_eft()
        # then
        self.assertEqual(fitting_text_original, fitting_text_generated)

    def test_eft_parser_rountrip_empty(self):
        # given
        self.maxDiff = None
        fitting_text_original = create_fitting_text("fitting_empty.txt")
        fitting, _ = Fitting.create_from_eft(fitting_text_original)
        # when
        fitting_text_generated = fitting.to_eft()
        # then
        self.assertEqual(fitting_text_original, fitting_text_generated)

    def test_required_skills(self):
        # given
        fitting_text = create_fitting_text("fitting_tristan.txt")
        fitting, _ = Fitting.create_from_eft(fitting_text)
        # when
        skills = fitting.required_skills()
        # then
        skills_str = sorted([str(skill) for skill in skills])
        self.assertListEqual(
            skills_str,
            [
                "Amarr Drone Specialization I",
                "Drones V",
                "Gallente Frigate I",
                "Gunnery II",
                "High Speed Maneuvering I",
                "Hull Upgrades II",
                "Light Drone Operation V",
                "Minmatar Drone Specialization I",
                "Propulsion Jamming II",
                "Shield Upgrades I",
                "Small Autocannon Specialization I",
                "Small Projectile Turret V",
                "Weapon Upgrades IV",
            ],
        )
