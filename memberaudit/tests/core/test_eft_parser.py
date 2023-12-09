from unittest.mock import patch

from bravado.exception import HTTPNotFound

from eveuniverse.models import EveEntity, EveType

from app_utils.esi_testing import BravadoResponseStub
from app_utils.testing import NoSocketsTestCase

from memberaudit.core.eft_parser import (
    MissingSectionsError,
    MissingTitleError,
    UnknownShipTypeError,
    _EftItem,
    _EftSection,
    _EftSlotType,
    _EftTextItem,
    _EftTextSection,
    _EveTypes,
    create_fitting_from_eft,
)
from memberaudit.tests.testdata.factories import create_fitting_text
from memberaudit.tests.testdata.load_eveuniverse import load_eveuniverse

MODULE_PATH = "memberaudit.core.eft_parser"


class TestEftParser(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_create_fitting(self):
        # given
        fitting_text = create_fitting_text("fitting_tristan.txt")
        # when
        fitting, errors = create_fitting_from_eft(fitting_text)
        # then
        self.assertListEqual(errors, [])
        self.assertEqual(fitting.name, "Tristan - Standard Kite (cap stable)")
        self.assertEqual(fitting.ship_type.name, "Tristan")
        self.assertEqual(
            fitting.low_slots[0].module_type.name, "Nanofiber Internal Structure II"
        )
        self.assertEqual(
            fitting.low_slots[1].module_type.name, "Drone Damage Amplifier II"
        )
        self.assertEqual(
            fitting.low_slots[2].module_type.name, "Drone Damage Amplifier II"
        )

        self.assertEqual(
            fitting.medium_slots[0].module_type.name,
            "5MN Cold-Gas Enduring Microwarpdrive",
        )
        self.assertEqual(
            fitting.medium_slots[1].module_type.name,
            "Medium Azeotropic Restrained Shield Extender",
        )
        self.assertEqual(fitting.medium_slots[2].module_type.name, "Warp Disruptor II")
        self.assertTrue(fitting.medium_slots[2].is_offline)

        self.assertEqual(
            fitting.high_slots[0].module_type.name, "125mm Gatling AutoCannon II"
        )
        self.assertEqual(fitting.high_slots[0].charge_type.name, "EMP S")
        self.assertEqual(
            fitting.high_slots[1].module_type.name, "125mm Gatling AutoCannon II"
        )
        self.assertEqual(fitting.high_slots[1].charge_type.name, "EMP S")
        self.assertTrue(fitting.high_slots[2].is_empty)

        self.assertEqual(
            fitting.rig_slots[0].module_type.name, "Small Capacitor Control Circuit I"
        )
        self.assertEqual(
            fitting.rig_slots[1].module_type.name, "Small Polycarbon Engine Housing I"
        )
        self.assertEqual(
            fitting.rig_slots[2].module_type.name, "Small EM Shield Reinforcer I"
        )

        self.assertEqual(fitting.drone_bay[0].item_type.name, "Acolyte II")
        self.assertEqual(fitting.drone_bay[0].quantity, 5)
        self.assertEqual(fitting.drone_bay[1].item_type.name, "Warrior II")
        self.assertEqual(fitting.drone_bay[1].quantity, 3)

    def test_should_raise_error_when_title_is_missing(self):
        # given
        fitting_text = create_fitting_text("fitting_tristan_no_title.txt")
        # when
        with self.assertRaises(MissingTitleError):
            create_fitting_from_eft(fitting_text)

    def test_should_raise_error_when_text_is_empty(self):
        # when
        with self.assertRaises(MissingSectionsError):
            create_fitting_from_eft("")

    def test_should_raise_error_when_ship_type_is_invalid(self):
        # given
        fitting_text = create_fitting_text("fitting_unknown_ship_type.txt")
        # when
        with self.assertRaises(UnknownShipTypeError):
            with patch(MODULE_PATH + "._load_eve_types") as m:
                m.return_value = _EveTypes(), {"Unknown"}
                create_fitting_from_eft(fitting_text)

    def test_should_report_unknown_types(self):
        # given
        fitting_text = create_fitting_text("fitting_tristan_unknown_types.txt")
        # when
        with patch(MODULE_PATH + ".EveEntity.objects.fetch_by_names_esi") as mock:
            mock.return_value = EveEntity.objects.none()
            fitting, errors = create_fitting_from_eft(fitting_text)
        # then
        self.assertIn("Unknown Type Alpha", ", ".join(errors))
        self.assertIn("Unknown Type Bravo", ", ".join(errors))
        self.assertEqual(
            fitting.low_slots[0].module_type.name, "Nanofiber Internal Structure II"
        )

    def test_should_handle_eve_format_with_missing_high_slots(self):
        # given
        fitting_text = create_fitting_text("fitting_eve_tristian.txt")
        # when
        fitting, errors = create_fitting_from_eft(fitting_text)
        # then
        self.assertListEqual(errors, [])
        self.assertListEqual(fitting.high_slots, [])
        self.assertListEqual(
            section_to_eft(fitting.low_slots),
            [
                "Nanofiber Internal Structure II",
                "Drone Damage Amplifier II",
                "Drone Damage Amplifier II",
            ],
        )
        self.assertListEqual(
            section_to_eft(fitting.medium_slots),
            [
                "5MN Cold-Gas Enduring Microwarpdrive",
                "Medium Azeotropic Restrained Shield Extender",
                "Warp Disruptor II",
            ],
        )
        self.assertListEqual(
            section_to_eft(fitting.rig_slots),
            [
                "Small Capacitor Control Circuit I",
                "Small Polycarbon Engine Housing I",
                "Small EM Shield Reinforcer I",
            ],
        )
        self.assertListEqual(
            section_to_eft(fitting.drone_bay),
            ["Warrior II x3", "Acolyte II x5"],
        )
        self.assertListEqual(
            section_to_eft(fitting.cargo_bay),
            ["EMP S x400"],
        )

    def test_should_handle_eve_format_with_missing_high_and_low_slots(self):
        # given
        fitting_text = create_fitting_text("fitting_eve_tristian_2.txt")
        # when
        fitting, errors = create_fitting_from_eft(fitting_text)
        # then
        self.assertListEqual(errors, [])
        self.assertListEqual(fitting.high_slots, [])
        self.assertListEqual(fitting.low_slots, [])
        self.assertListEqual(
            section_to_eft(fitting.medium_slots),
            [
                "5MN Cold-Gas Enduring Microwarpdrive",
                "Medium Azeotropic Restrained Shield Extender",
                "Warp Disruptor II",
            ],
        )
        self.assertListEqual(
            section_to_eft(fitting.rig_slots),
            [
                "Small Capacitor Control Circuit I",
                "Small Polycarbon Engine Housing I",
                "Small EM Shield Reinforcer I",
            ],
        )
        self.assertListEqual(
            section_to_eft(fitting.drone_bay),
            ["Warrior II x3", "Acolyte II x5"],
        )
        self.assertListEqual(
            section_to_eft(fitting.cargo_bay),
            ["EMP S x400"],
        )


def section_to_eft(items) -> list:
    return [obj.to_eft() for obj in items]


class TestEveTypes(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_create_from_names(self):
        # given
        drones = EveType.objects.get(name="Drones")
        gunnery = EveType.objects.get(name="Gunnery")
        # when
        eve_types, _ = _EveTypes.create_from_names(["Drones", "Gunnery"])
        # then
        self.assertEqual(eve_types.from_name("Drones"), drones)
        self.assertEqual(eve_types.from_name("Gunnery"), gunnery)

    def test_should_try_to_fetch_unknown_types_from_esi(self):
        # given
        unknown_type = EveType(id=99, name="Unknown-Type")
        # when
        with patch(
            MODULE_PATH + ".EveEntity.objects.fetch_by_names_esi"
        ) as mock_fetch_by_names_esi, patch(
            MODULE_PATH + ".EveType.objects.get_or_create_esi"
        ) as mock_get_or_create_esi:
            mock_fetch_by_names_esi.return_value.filter.return_value.values_list.return_value = [
                99
            ]
            mock_get_or_create_esi.return_value = (unknown_type, False)
            eve_types, _ = _EveTypes.create_from_names(["Unknown-Type"])
        # then
        self.assertEqual(eve_types.from_name("Unknown-Type"), unknown_type)

    def test_should_handle_type_not_found(self):
        # given
        http404 = HTTPNotFound(
            BravadoResponseStub(status_code=404), message="Test exception"
        )
        # when
        with patch(
            MODULE_PATH + ".EveEntity.objects.fetch_by_names_esi"
        ) as mock_fetch_by_names_esi, patch(
            MODULE_PATH + ".EveType.objects.get_or_create_esi"
        ) as mock_get_or_create_esi:
            mock_fetch_by_names_esi.return_value.filter.return_value.values_list.return_value = [
                99
            ]
            mock_get_or_create_esi.side_effect = http404
            eve_types, unknown_types = _EveTypes.create_from_names(["Unknown-Type"])
        # then
        self.assertIsNone(eve_types.from_name("Unknown-Type"))
        self.assertIn("Unknown-Type", unknown_types)

    def test_should_handle_unknown_types(self):
        # given
        drones = EveType.objects.get(name="Drones")
        # when
        with patch(
            MODULE_PATH + ".EveEntity.objects.fetch_by_names_esi"
        ) as mock_fetch_by_names_esi:
            mock_fetch_by_names_esi.return_value.filter.return_value.values_list.return_value = (
                []
            )
            eve_types, unknown_types = _EveTypes.create_from_names(
                ["Drones", "Unknown-Type"]
            )
        # then
        self.assertEqual(eve_types.from_name("Drones"), drones)
        self.assertIsNone(eve_types.from_name("Unknown-Type"))
        self.assertIn("Unknown-Type", unknown_types)

    def test_should_raise_error_when_not_passing_iterable(self):
        # when/then
        with self.assertRaises(TypeError):
            _EveTypes.create_from_names("not an allowed iterable")


class TestEftTextItem(NoSocketsTestCase):
    def test_should_create_slot_module(self):
        #  when
        item = _EftTextItem.create_from_line("Warp Disruptor II")
        # then
        self.assertEqual(item, _EftTextItem(item_type="Warp Disruptor II"))

    def test_should_create_slot_module_with_charge(self):
        #  when
        item = _EftTextItem.create_from_line("125mm Gatling AutoCannon II, EMP S")
        # then
        self.assertEqual(
            item,
            _EftTextItem(item_type="125mm Gatling AutoCannon II", charge_type="EMP S"),
        )

    def test_should_create_slot_module_offline(self):
        #  when
        item = _EftTextItem.create_from_line("Warp Disruptor II /OFFLINE")
        # then
        self.assertEqual(
            item, _EftTextItem(item_type="Warp Disruptor II", is_offline=True)
        )

    def test_should_create_slot_empty_high_slot(self):
        #  when
        item = _EftTextItem.create_from_line("[Empty High slot]")
        # then
        expected = _EftTextItem(slot_type=_EftSlotType.HIGH_SLOT)
        self.assertEqual(item, expected)

    def test_should_create_slot_empty_sub_system_slot(self):
        #  when
        item = _EftTextItem.create_from_line("[Empty Subsystem slot]")
        # then
        expected = _EftTextItem(slot_type=_EftSlotType.SUBSYSTEM_SLOT)
        self.assertEqual(item, expected)

    def test_should_create_non_slot_item(self):
        #  when
        item = _EftTextItem.create_from_line("Acolyte II x5")
        # then
        self.assertEqual(item, _EftTextItem(item_type="Acolyte II", quantity=5))

    def test_should_return_type_names_1(self):
        #  when
        item = _EftTextItem.create_from_line("125mm Gatling AutoCannon II")
        # then
        self.assertEqual(item.type_names(), {"125mm Gatling AutoCannon II"})

    def test_should_return_type_names_2(self):
        #  when
        item = _EftTextItem.create_from_line("125mm Gatling AutoCannon II, EMP S")
        # then
        self.assertEqual(item.type_names(), {"125mm Gatling AutoCannon II", "EMP S"})

    def test_should_return_type_names_3(self):
        #  when
        item = _EftTextItem.create_from_line("Acolyte II x5")
        # then
        self.assertEqual(item.type_names(), {"Acolyte II"})


class TestEftTextSection(NoSocketsTestCase):
    def test_should_create_section(self):
        # given
        lines = ["Acolyte II x5", "Warrior II x5"]
        # when
        section = _EftTextSection.create_from_lines(lines)
        # then
        self.assertEqual(
            section.items[0], _EftTextItem(item_type="Acolyte II", quantity=5)
        )
        self.assertEqual(
            section.items[1], _EftTextItem(item_type="Warrior II", quantity=5)
        )

    def test_should_return_type_names(self):
        # given
        section = _EftTextSection(
            [
                _EftTextItem(item_type="Acolyte II", quantity=5),
                _EftTextItem(
                    item_type="125mm Gatling AutoCannon II", charge_type="EMP S"
                ),
                _EftTextItem(item_type="Warp Disruptor II"),
            ]
        )
        # when / then
        self.assertSetEqual(
            section.type_names(),
            {"Acolyte II", "125mm Gatling AutoCannon II", "EMP S", "Warp Disruptor II"},
        )


class TestEftItem(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_create_from_text_item_1(self):
        # given
        text_item = _EftTextItem(item_type="Warp Disruptor II")
        eve_types, _ = _EveTypes.create_from_names(["Warp Disruptor II"])
        # when
        item = _EftItem.create_from_text_item(text_item=text_item, eve_types=eve_types)
        # then
        self.assertEqual(
            item, _EftItem(item_type=EveType.objects.get(name="Warp Disruptor II"))
        )

    def test_should_create_from_text_item_2(self):
        # given
        text_item = _EftTextItem(item_type="Warp Disruptor II", quantity=3)
        eve_types, _ = _EveTypes.create_from_names(["Warp Disruptor II"])
        # when
        item = _EftItem.create_from_text_item(text_item=text_item, eve_types=eve_types)
        # then
        self.assertEqual(
            item,
            _EftItem(
                item_type=EveType.objects.get(name="Warp Disruptor II"), quantity=3
            ),
        )

    def test_should_create_from_text_item_3(self):
        # given
        text_item = _EftTextItem(
            item_type="125mm Gatling AutoCannon II", charge_type="EMP S"
        )
        eve_types, _ = _EveTypes.create_from_names(
            ["125mm Gatling AutoCannon II", "EMP S"]
        )
        # when
        item = _EftItem.create_from_text_item(text_item=text_item, eve_types=eve_types)
        # then
        self.assertEqual(
            item,
            _EftItem(
                item_type=EveType.objects.get(name="125mm Gatling AutoCannon II"),
                charge_type=EveType.objects.get(name="EMP S"),
            ),
        )

    def test_should_be_slot(self):
        # given
        item = _EftItem(item_type=EveType.objects.get(name="Warp Disruptor II"))
        # when/then
        self.assertTrue(item.is_slot)

    def test_should_not_be_slot(self):
        # given
        item = _EftItem(
            item_type=EveType.objects.get(name="Warp Disruptor II"), quantity=3
        )
        # when/then
        self.assertFalse(item.is_slot)

    def test_should_be_booster(self):
        # given
        item = _EftItem(
            item_type=EveType.objects.get(name="Agency 'Pyrolancea' DB5 Dose II")
        )
        # when/then
        self.assertTrue(item.is_booster())

    def test_should_be_cyber_implant(self):
        # given
        item = _EftItem(item_type=EveType.objects.get(name="High-grade Snake Alpha"))
        # when/then
        self.assertTrue(item.is_cyber_implant())

    def test_should_be_drone(self):
        # given
        item = _EftItem(item_type=EveType.objects.get(name="Acolyte II"))
        # when/then
        self.assertTrue(item.is_drone())

    def test_should_be_fighter(self):
        # given
        item = _EftItem(item_type=EveType.objects.get(name="Firbolg I"))
        # when/then
        self.assertTrue(item.is_fighter())

    def test_should_be_subsystem(self):
        # given
        item = _EftItem(
            item_type=EveType.objects.get(
                name="Tengu Core - Augmented Graviton Reactor"
            )
        )
        # when/then
        self.assertTrue(item.is_subsystem())

    def test_should_be_high_slot(self):
        # given
        item = _EftItem(
            item_type=EveType.objects.get(name="125mm Gatling AutoCannon II")
        )
        # when/then
        self.assertTrue(item.is_high_slot())
        self.assertFalse(item.is_med_slot())
        self.assertFalse(item.is_low_slot())
        self.assertFalse(item.is_rig_slot())

    def test_should_be_med_slot(self):
        # given
        item = _EftItem(item_type=EveType.objects.get(name="Warp Disruptor II"))
        # when/then
        self.assertFalse(item.is_high_slot())
        self.assertTrue(item.is_med_slot())
        self.assertFalse(item.is_low_slot())
        self.assertFalse(item.is_rig_slot())

    def test_should_be_low_slot(self):
        # given
        item = _EftItem(item_type=EveType.objects.get(name="Drone Damage Amplifier II"))
        # when/then
        self.assertFalse(item.is_high_slot())
        self.assertFalse(item.is_med_slot())
        self.assertTrue(item.is_low_slot())
        self.assertFalse(item.is_rig_slot())

    def test_should_be_rig_slot(self):
        # given
        item = _EftItem(
            item_type=EveType.objects.get(name="Small EM Shield Reinforcer I")
        )
        # when/then
        self.assertFalse(item.is_high_slot())
        self.assertFalse(item.is_med_slot())
        self.assertFalse(item.is_low_slot())
        self.assertTrue(item.is_rig_slot())

    def test_should_handle_empty_item(self):
        # given
        empty_item = _EftItem()
        # when/then
        self.assertTrue(empty_item.is_empty)
        self.assertFalse(empty_item.is_booster())
        self.assertFalse(empty_item.is_cyber_implant())
        self.assertFalse(empty_item.is_drone())
        self.assertFalse(empty_item.is_fighter())
        self.assertFalse(empty_item.is_high_slot())
        self.assertFalse(empty_item.is_med_slot())
        self.assertFalse(empty_item.is_low_slot())
        self.assertFalse(empty_item.is_rig_slot())
        self.assertFalse(empty_item.is_subsystem())


class TestEftSection(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_should_be_boosters(self):
        # given
        section = _EftSection(
            [
                _EftItem(
                    item_type=EveType.objects.get(
                        name="Agency 'Pyrolancea' DB5 Dose II"
                    )
                )
            ]
        )
        # when/then
        self.assertEqual(section.guess_category(), _EftSection.Category.BOOSTERS)

    def test_should_be_implants(self):
        # given
        section = _EftSection(
            [_EftItem(item_type=EveType.objects.get(name="High-grade Snake Alpha"))]
        )
        # when/then
        self.assertEqual(section.guess_category(), _EftSection.Category.IMPLANTS)

    def test_should_be_drone_bay(self):
        # given
        section = _EftSection(
            [_EftItem(item_type=EveType.objects.get(name="Acolyte II"), quantity=5)]
        )
        # when/then
        self.assertEqual(section.guess_category(), _EftSection.Category.DRONES_BAY)

    def test_should_be_fighter_bay(self):
        # given
        section = _EftSection(
            [_EftItem(item_type=EveType.objects.get(name="Firbolg I"), quantity=5)]
        )
        # when/then
        self.assertEqual(section.guess_category(), _EftSection.Category.FIGHTER_BAY)

    def test_should_be_subsystem_slots(self):
        # given
        section = _EftSection(
            [
                _EftItem(
                    item_type=EveType.objects.get(
                        name="Tengu Core - Augmented Graviton Reactor"
                    )
                )
            ]
        )
        # when/then
        self.assertEqual(section.guess_category(), _EftSection.Category.SUBSYSTEM_SLOTS)

    def test_should_be_high_slots(self):
        # given
        section = _EftSection(
            [
                _EftItem(
                    item_type=EveType.objects.get(name="125mm Gatling AutoCannon II")
                )
            ]
        )
        # when/then
        self.assertEqual(section.guess_category(), _EftSection.Category.HIGH_SLOTS)

    def test_should_be_med_slots(self):
        # given
        section = _EftSection(
            [_EftItem(item_type=EveType.objects.get(name="Warp Disruptor II"))]
        )
        # when/then
        self.assertEqual(section.guess_category(), _EftSection.Category.MEDIUM_SLOTS)

    def test_should_be_low_slots(self):
        # given
        section = _EftSection(
            [_EftItem(item_type=EveType.objects.get(name="Drone Damage Amplifier II"))]
        )
        # when/then
        self.assertEqual(section.guess_category(), _EftSection.Category.LOW_SLOTS)

    def test_should_be_rig_slots(self):
        # given
        section = _EftSection(
            [
                _EftItem(
                    item_type=EveType.objects.get(name="Small EM Shield Reinforcer I")
                )
            ]
        )
        # when/then
        self.assertEqual(section.guess_category(), _EftSection.Category.RIG_SLOTS)

    def test_should_be_slots(self):
        # given
        section = _EftSection(
            [
                _EftItem(
                    item_type=EveType.objects.get(name="Small EM Shield Reinforcer I")
                )
            ]
        )
        # when/then
        self.assertTrue(section.is_slots)


class TestCreateFittingFromEft(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_eveuniverse()

    def test_eft_parser_roundtrip_archon_normal(self):
        # given
        self.maxDiff = None
        fitting_text_original = create_fitting_text("fitting_archon.txt")
        fitting, _ = create_fitting_from_eft(fitting_text_original)
        # when
        fitting_text_generated = fitting.to_eft()
        # then
        self.assertEqual(fitting_text_original, fitting_text_generated)

    def test_eft_parser_rountrip_archon_max(self):
        # given
        self.maxDiff = None
        fitting_text_original = create_fitting_text("fitting_archon_max.txt")
        fitting, _ = create_fitting_from_eft(fitting_text_original)
        # when
        fitting_text_generated = fitting.to_eft()
        # then
        self.assertEqual(fitting_text_original, fitting_text_generated)

    def test_eft_parser_rountrip_tristan(self):
        # given
        self.maxDiff = None
        fitting_text_original = create_fitting_text("fitting_tristan.txt")
        fitting, _ = create_fitting_from_eft(fitting_text_original)
        # when
        fitting_text_generated = fitting.to_eft()
        # then
        self.assertEqual(fitting_text_original, fitting_text_generated)

    def test_eft_parser_rountrip_svipul_empty_slots_and_offline(self):
        # given
        self.maxDiff = None
        fitting_text_original = create_fitting_text("fitting_svipul_2.txt")
        fitting, _ = create_fitting_from_eft(fitting_text_original)
        # when
        fitting_text_generated = fitting.to_eft()
        # then
        self.assertEqual(fitting_text_original, fitting_text_generated)

    def test_eft_parser_rountrip_tengu(self):
        # given
        self.maxDiff = None
        fitting_text_original = create_fitting_text("fitting_tengu.txt")
        fitting, _ = create_fitting_from_eft(fitting_text_original)
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
        fitting, _ = create_fitting_from_eft(fitting_text_original)
        # when
        fitting_text_generated = fitting.to_eft()
        # then
        self.assertEqual(fitting_text_original, fitting_text_generated)

    def test_required_skills(self):
        # given
        fitting_text = create_fitting_text("fitting_tristan.txt")
        fitting, _ = create_fitting_from_eft(fitting_text)
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
