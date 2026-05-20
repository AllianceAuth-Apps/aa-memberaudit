"""Shared ESI client for Member Audit."""

from pathlib import Path

from esi.openapi_clients import ESIClientProvider

from memberaudit import __version__

spec_file = Path(__file__).parent / "openapi_2025-12-16.json"
esi = ESIClientProvider(
    compatibility_date="2025-12-16",
    ua_appname="aa-memberaudit",
    ua_version=__version__,
    operations=[
        "GetCharactersCharacterId",
        "GetCharactersCharacterIdAssets",
        "GetCharactersCharacterIdAttributes",
        "GetCharactersCharacterIdClones",
        "GetCharactersCharacterIdContacts",
        "GetCharactersCharacterIdContactsLabels",
        "GetCharactersCharacterIdContracts",
        "GetCharactersCharacterIdContractsContractIdBids",
        "GetCharactersCharacterIdContractsContractIdItems",
        "GetCharactersCharacterIdCorporationhistory",
        "GetCharactersCharacterIdFwStats",
        "GetCharactersCharacterIdImplants",
        "GetCharactersCharacterIdLocation",
        "GetCharactersCharacterIdLoyaltyPoints",
        "GetCharactersCharacterIdMail",
        "GetCharactersCharacterIdMailLabels",
        "GetCharactersCharacterIdMailLists",
        "GetCharactersCharacterIdMailMailId",
        "GetCharactersCharacterIdMining",
        "GetCharactersCharacterIdOnline",
        "GetCharactersCharacterIdPlanets",
        "GetCharactersCharacterIdRoles",
        "GetCharactersCharacterIdShip",
        "GetCharactersCharacterIdSkillqueue",
        "GetCharactersCharacterIdSkills",
        "GetCharactersCharacterIdStandings",
        "GetCharactersCharacterIdTitles",
        "GetCharactersCharacterIdWallet",
        "GetCharactersCharacterIdWalletJournal",
        "GetCharactersCharacterIdWalletTransactions",
        "GetStatus",
        "GetUniverseStationsStationId",
        "GetUniverseStructuresStructureId",
        "PostCharactersCharacterIdAssetsNames",
    ],
    spec_file=spec_file,
)
