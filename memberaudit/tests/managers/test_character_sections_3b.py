from collections import namedtuple
from http import HTTPStatus
from typing import NamedTuple

import pook

from eveuniverse.tests.testdata.factories_2 import EveEntityCharacterFactory

from app_utils.testing import NoSocketsTestCase

from memberaudit.models import CharacterSkillSetCheck, CharacterStanding, CharacterTitle
from memberaudit.tests.testdata.factories_2 import (
    CharacterFactory,
    CharacterSkillFactory,
    CharacterSkillSetCheckFactory,
    CharacterStandingFactory,
    CharacterTitleFactory,
    SkillSetFactory,
    SkillSetSkillFactory,
    SpaceshipCommandSkillTypeFactory,
    make_esi_url,
)
from memberaudit.tests.utils import TestCaseWithClearCache, extract


class TestCharacter_UpdateSkillSets_Single(NoSocketsTestCase):
    def test_variations_two_skill_sets(self):
        skill_1_type = SpaceshipCommandSkillTypeFactory()
        skill_2_type = SpaceshipCommandSkillTypeFactory()
        skill_set = SkillSetFactory()
        skill_1 = SkillSetSkillFactory(
            skill_set=skill_set,
            eve_type=skill_1_type,
            required_level=3,
            recommended_level=5,
        )
        skill_2 = SkillSetSkillFactory(
            skill_set=skill_set,
            eve_type=skill_2_type,
            required_level=3,
            recommended_level=5,
        )

        class Case(NamedTuple):
            skill_1_level: int
            skill_2_level: int
            failed_required_skills: list
            failed_recommended_skills: list

        cases = [
            Case(5, 5, [], []),
            Case(3, 3, [], [skill_1, skill_2]),
            Case(5, 3, [], [skill_2]),
            Case(3, 5, [], [skill_1]),
            Case(5, 0, [skill_2], [skill_2]),
            Case(0, 5, [skill_1], [skill_1]),
            Case(1, 1, [skill_1, skill_2], [skill_1, skill_2]),
            Case(0, 0, [skill_1, skill_2], [skill_1, skill_2]),
        ]

        for i, tc in enumerate(cases, 1):
            # given
            character = CharacterFactory()
            if tc.skill_1_level:
                CharacterSkillFactory(
                    character=character,
                    eve_type=skill_1_type,
                    active_skill_level=tc.skill_1_level,
                )
            if tc.skill_2_level:
                CharacterSkillFactory(
                    character=character,
                    eve_type=skill_2_type,
                    active_skill_level=tc.skill_2_level,
                )

            # when
            got = character.update_skill_sets()

            # then
            msg = f"num={i}"
            self.assertTrue(got.is_updated, msg=msg)
            self.assertEqual(character.skill_set_checks.count(), 1, msg=msg)
            check: CharacterSkillSetCheck = character.skill_set_checks.first()
            self.assertCountEqual(
                check.failed_required_skills.all(), tc.failed_required_skills, msg=msg
            )
            self.assertCountEqual(
                check.failed_recommended_skills.all(),
                tc.failed_recommended_skills,
                msg=msg,
            )
            character.delete()

    def test_variations_one_skill_set(self):
        skill_type = SpaceshipCommandSkillTypeFactory()

        class Case(NamedTuple):
            name: str
            required: int
            recommended: int
            active: int
            has_required_failed: bool
            has_recommended_failed: bool

        cases = [
            Case("has recommended", 3, 5, 5, False, False),
            Case("has required", 3, 5, 3, False, True),
            Case("below required", 3, 5, 2, True, True),
            Case("skill not trained", 3, 5, 0, True, True),
            Case("no required", None, 5, 1, False, True),
            Case("no required and skill not trained", None, 5, 0, False, True),
        ]

        for tc in cases:
            # given
            skill_set = SkillSetFactory()
            SkillSetSkillFactory(
                skill_set=skill_set,
                eve_type=skill_type,
                required_level=tc.required,
                recommended_level=tc.recommended,
            )
            character = CharacterFactory()
            if tc.active:
                CharacterSkillFactory(
                    character=character,
                    eve_type=skill_type,
                    active_skill_level=tc.active,
                )

            # when
            got = character.update_skill_sets()

            # then
            self.assertTrue(got.is_updated, msg=tc.name)
            self.assertEqual(character.skill_set_checks.count(), 1, msg=tc.name)
            check: CharacterSkillSetCheck = character.skill_set_checks.first()
            self.assertEqual(
                check.failed_required_skills.exists(),
                tc.has_required_failed,
                msg=tc.name,
            )
            self.assertEqual(
                check.failed_recommended_skills.exists(),
                tc.has_recommended_failed,
                msg=tc.name,
            )
            character.delete()
            skill_set.delete()


class TestCharacter_UpdateSkillSets_Multi(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.amarr_carrier_skill_set = SkillSetFactory()
        cls.amarr_carrier_skill_type = SpaceshipCommandSkillTypeFactory()
        cls.amarr_carrier_skill_set_skill = SkillSetSkillFactory(
            skill_set=cls.amarr_carrier_skill_set,
            eve_type=cls.amarr_carrier_skill_type,
            required_level=3,
            recommended_level=5,
        )

        cls.caldari_carrier_skill_set = SkillSetFactory()
        cls.caldari_carrier_skill_type = SpaceshipCommandSkillTypeFactory()
        cls.caldari_carrier_skill_set_skill = SkillSetSkillFactory(
            skill_set=cls.caldari_carrier_skill_set,
            eve_type=cls.caldari_carrier_skill_type,
            required_level=3,
            recommended_level=5,
        )

    def test_should_create_for_can_fly_amarr_and_not_not_caldari(self):
        # given
        character = CharacterFactory()
        CharacterSkillFactory(
            character=character,
            eve_type=self.amarr_carrier_skill_type,
            active_skill_level=3,
        )

        # when
        character.update_skill_sets()

        # then
        check_1: CharacterSkillSetCheck = character.skill_set_checks.filter(
            skill_set=self.amarr_carrier_skill_set
        ).first()
        self.assertCountEqual(
            check_1.failed_required_skills.all(),
            [],
        )
        self.assertCountEqual(
            check_1.failed_recommended_skills.all(),
            [self.amarr_carrier_skill_set_skill],
        )

        check_2: CharacterSkillSetCheck = character.skill_set_checks.filter(
            skill_set=self.caldari_carrier_skill_set
        ).first()
        self.assertCountEqual(
            check_2.failed_required_skills.all(),
            [self.caldari_carrier_skill_set_skill],
        )
        self.assertCountEqual(
            check_2.failed_recommended_skills.all(),
            [self.caldari_carrier_skill_set_skill],
        )

    def test_should_create_for_can_not_fly_either(self):
        # given
        character = CharacterFactory()
        CharacterSkillFactory(
            character=character,
            eve_type=self.amarr_carrier_skill_type,
            active_skill_level=1,
        )

        # when
        character.update_skill_sets()

        # then
        check_1: CharacterSkillSetCheck = character.skill_set_checks.filter(
            skill_set=self.amarr_carrier_skill_set
        ).first()
        self.assertCountEqual(
            check_1.failed_required_skills.all(),
            [self.amarr_carrier_skill_set_skill],
        )
        self.assertCountEqual(
            check_1.failed_recommended_skills.all(),
            [self.amarr_carrier_skill_set_skill],
        )

        check_2: CharacterSkillSetCheck = character.skill_set_checks.filter(
            skill_set=self.caldari_carrier_skill_set
        ).first()
        self.assertCountEqual(
            check_2.failed_required_skills.all(),
            [self.caldari_carrier_skill_set_skill],
        )
        self.assertCountEqual(
            check_2.failed_recommended_skills.all(),
            [self.caldari_carrier_skill_set_skill],
        )

    def test_should_update_existing_skill_set_check(self):
        # given
        character = CharacterFactory()
        check_0 = CharacterSkillSetCheckFactory(
            character=character, skill_set=self.amarr_carrier_skill_set
        )
        check_0.failed_required_skills.add(self.amarr_carrier_skill_set_skill)
        check_0.failed_recommended_skills.add(self.amarr_carrier_skill_set_skill)

        CharacterSkillFactory(
            character=character,
            eve_type=self.amarr_carrier_skill_type,
            active_skill_level=3,
        )

        # when
        character.update_skill_sets()

        # then
        check_1: CharacterSkillSetCheck = character.skill_set_checks.filter(
            skill_set=self.amarr_carrier_skill_set
        ).first()
        self.assertCountEqual(
            check_1.failed_required_skills.all(),
            [],
        )
        self.assertCountEqual(
            check_1.failed_recommended_skills.all(),
            [self.amarr_carrier_skill_set_skill],
        )

        check_2: CharacterSkillSetCheck = character.skill_set_checks.filter(
            skill_set=self.caldari_carrier_skill_set
        ).first()
        self.assertCountEqual(
            check_2.failed_required_skills.all(),
            [self.caldari_carrier_skill_set_skill],
        )
        self.assertCountEqual(
            check_2.failed_recommended_skills.all(),
            [self.caldari_carrier_skill_set_skill],
        )


class TestCharacter_UpdateStandings(TestCaseWithClearCache):
    @pook.on
    def test_can_create_from_scratch(self):
        # given
        character = CharacterFactory()
        standing = -5
        eve_entity = EveEntityCharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/standings"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "from_id": eve_entity.id,
                    "from_type": "agent",
                    "standing": standing,
                }
            ],
        )

        # when
        character.update_standings()

        # then
        self.assertEqual(character.standings.count(), 1)
        obj: CharacterStanding = character.standings.first()
        self.assertEqual(obj.eve_entity, eve_entity)
        self.assertEqual(obj.standing, standing)

    @pook.on
    def test_can_update_existing(self):
        # given
        character = CharacterFactory()
        obj = CharacterStandingFactory(character=character)
        standing = -5
        pook.get(
            make_esi_url(f"characters/{character.character_id}/standings"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "from_id": obj.eve_entity.id,
                    "from_type": "agent",
                    "standing": standing,
                }
            ],
        )

        # when
        character.update_standings()

        # then
        obj.refresh_from_db()

    @pook.on
    def test_can_remove_stale_standings(self):
        # given
        character = CharacterFactory()
        CharacterStandingFactory(character=character)  # to be removed
        standing = -5
        eve_entity = EveEntityCharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/standings"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "from_id": eve_entity.id,
                    "from_type": "agent",
                    "standing": standing,
                }
            ],
        )

        # when
        character.update_standings()

        # then
        got = extract(character.standings, "eve_entity__id")
        want = {eve_entity.id}
        self.assertSetEqual(got, want)

    @pook.on
    def test_can_handle_no_standings(self):
        # given
        character = CharacterFactory()
        pook.get(
            make_esi_url(f"characters/{character.character_id}/standings"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[],
        )

        # when
        character.update_standings()

        # then
        self.assertEqual(character.standings.count(), 0)


class TestCharacter_UpdateTitles(TestCaseWithClearCache):
    @pook.on
    def test_should_add_new_title_from_scratch(self):
        # given
        character = CharacterFactory()
        name = "Awesome Title"
        title_id = 7
        pook.get(
            make_esi_url(f"characters/{character.character_id}/titles"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "name": name,
                    "title_id": title_id,
                }
            ],
        )
        # when
        character.update_titles()

        # then
        self.assertEqual(character.titles.count(), 1)
        title: CharacterTitle = character.titles.first()
        self.assertEqual(title.name, name)
        self.assertEqual(title.title_id, title_id)

    @pook.on
    def test_should_update_existing_titles(self):
        # given
        character = CharacterFactory()
        title = CharacterTitleFactory(character=character)
        name = "Awesome Title"
        pook.get(
            make_esi_url(f"characters/{character.character_id}/titles"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "name": name,
                    "title_id": title.title_id,
                }
            ],
        )
        # when
        character.update_titles()

        # then
        title.refresh_from_db()
        self.assertEqual(title.name, name)

    @pook.on
    def test_should_remove_stale_titles(self):
        # given
        character = CharacterFactory()
        CharacterTitleFactory(character=character)  # to be removed
        name = "Awesome Title"
        title_id = 7
        pook.get(
            make_esi_url(f"characters/{character.character_id}/titles"),
            reply=HTTPStatus.OK,
            response_headers={"X-Pages": "1"},
            response_json=[
                {
                    "name": name,
                    "title_id": title_id,
                }
            ],
        )
        # when
        character.update_titles()

        # then
        self.assertEqual(character.titles.count(), 1)
        title: CharacterTitle = character.titles.first()
        self.assertEqual(title.name, name)
        self.assertEqual(title.title_id, title_id)

    @pook.on
    def test_should_remove_xml_from_titles_and_strip(self):
        Case = namedtuple("X", ["title", "want"])
        cases = [
            Case("<color=0xFFee82ee> Awesome Title ", "Awesome Title"),
            Case("<color=0xFFee82ee> Officer", "Officer"),
            Case("<color=0xff649abb>Officer</color>", "Officer"),
        ]

        character = CharacterFactory()
        title = CharacterTitleFactory(character=character, name="Old title", title_id=1)
        for tc in cases:
            with self.subTest(title=tc.title):
                pook.get(
                    make_esi_url(f"characters/{character.character_id}/titles"),
                    reply=HTTPStatus.OK,
                    response_headers={"X-Pages": "1"},
                    response_json=[
                        {
                            "name": tc.title,
                            "title_id": 1,
                        }
                    ],
                )

                # when
                character.update_titles()

                # then
                title.refresh_from_db()
                self.assertEqual(title.name, tc.want)
