# from django.test import TestCase

from eveuniverse.models import EveType

from app_utils.testing import NoSocketsTestCase

from memberaudit.core.fittings import Fitting, Module, _BaseFittingItem
from memberaudit.tests.testdata.factories import create_fitting
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse


class TestBaseFittingItem(NoSocketsTestCase):
    def test_can_not_instantiate(self):
        # given
        with self.assertRaises(RuntimeError):
            _BaseFittingItem()


class TestModule(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
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
    def setUpClass(cls):
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
