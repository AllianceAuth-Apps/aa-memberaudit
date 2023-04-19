from django.test import TestCase
from eveuniverse.models import EveEntity, EveMarketPrice, EveSolarSystem, EveType

from app_utils.testing import NoSocketsTestCase

from ...models import (
    CharacterAsset,
    CharacterContactLabel,
    CharacterContract,
    CharacterContractBid,
    CharacterMailLabel,
    Location,
)
from ..testdata.factories import (
    create_character_contract,
    create_character_contract_bid,
)
from ..testdata.load_entities import load_entities
from ..testdata.load_eveuniverse import load_eveuniverse
from ..testdata.load_locations import load_locations
from ..utils import create_memberaudit_character


class TestCharacterAssetManager(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character = create_memberaudit_character(1001)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.merlin = EveType.objects.get(id=603)

    def test_can_calculate_pricing(self):
        CharacterAsset.objects.create(
            character=self.character,
            item_id=1100000000666,
            location=self.jita_44,
            eve_type=self.merlin,
            is_singleton=False,
            quantity=5,
        )
        EveMarketPrice.objects.create(eve_type=self.merlin, average_price=500000)
        asset = CharacterAsset.objects.annotate_pricing().first()
        self.assertEqual(asset.price, 500000)
        self.assertEqual(asset.total, 2500000)

    def test_does_not_price_blueprint_copies(self):
        CharacterAsset.objects.create(
            character=self.character,
            item_id=1100000000666,
            location=self.jita_44,
            eve_type=self.merlin,
            is_blueprint_copy=True,
            is_singleton=False,
            quantity=1,
        )
        EveMarketPrice.objects.create(eve_type=self.merlin, average_price=500000)
        asset = CharacterAsset.objects.annotate_pricing().first()
        self.assertIsNone(asset.price)
        self.assertIsNone(asset.total)


class TestCharacterUpdateBase(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eveuniverse()
        load_entities()
        load_locations()
        cls.character_1001 = create_memberaudit_character(1001)
        cls.character_1002 = create_memberaudit_character(1002)
        cls.corporation_2001 = EveEntity.objects.get(id=2001)
        cls.corporation_2002 = EveEntity.objects.get(id=2002)
        cls.token = (
            cls.character_1001.eve_character.character_ownership.user.token_set.first()
        )
        cls.jita = EveSolarSystem.objects.get(id=30000142)
        cls.jita_44 = Location.objects.get(id=60003760)
        cls.amamake = EveSolarSystem.objects.get(id=30002537)
        cls.structure_1 = Location.objects.get(id=1000000000001)


class TestCharacterContactLabelManager(TestCharacterUpdateBase):
    def test_should_do_nothing(self):
        # when
        CharacterContactLabel.objects.update_for_character(
            character=self.character_1001, labels=[]
        )
        # then
        self.assertEqual(CharacterContactLabel.objects.count(), 0)


class TestCharacterContractBidManager(TestCharacterUpdateBase):
    def test_should_do_nothing_when_there_are_no_bids(self):
        # given
        contract = create_character_contract(
            character=self.character_1001, contract_type=CharacterContract.TYPE_AUCTION
        )
        # when
        CharacterContractBid.objects.update_for_contract(
            contract=contract, bids_list=dict()
        )
        # then
        self.assertEqual(CharacterContractBid.objects.count(), 0)

    def test_should_do_nothing_when_there_are_no_new_bids(self):
        # given
        contract = create_character_contract(
            character=self.character_1001, contract_type=CharacterContract.TYPE_AUCTION
        )
        bidder = EveEntity.objects.get(id=1002)
        bid = create_character_contract_bid(contract=contract, bidder=bidder)
        bids_list = {
            bid.bid_id: {
                "amount": bid.amount,
                "bid_id": bid.bid_id,
                "bidder_id": bidder.id,
                "date_bid": bid.date_bid,
            }
        }
        # when
        CharacterContractBid.objects.update_for_contract(
            contract=contract, bids_list=bids_list
        )
        # then
        self.assertEqual(CharacterContractBid.objects.count(), 1)


class TestCharacterMailLabelManager(TestCharacterUpdateBase):
    def test_normal(self):
        label_1 = CharacterMailLabel.objects.create(
            character=self.character_1001, label_id=1, name="Alpha"
        )
        label_2 = CharacterMailLabel.objects.create(
            character=self.character_1001, label_id=2, name="Bravo"
        )
        labels = CharacterMailLabel.objects.get_all_labels()
        self.assertDictEqual(
            labels, {label_1.label_id: label_1, label_2.label_id: label_2}
        )

    def test_empty(self):
        labels = CharacterMailLabel.objects.get_all_labels()
        self.assertDictEqual(labels, dict())
