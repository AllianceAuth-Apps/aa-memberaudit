"""Shared ESI client for Member Audit."""

from pathlib import Path

from esi.clients import EsiClientProvider

from memberaudit import __version__

spec_file = Path(__file__).parent / "swagger.json"

esi = EsiClientProvider(
    app_info_text=f"aa-memberaudit v{__version__}", spec_file=spec_file
)
