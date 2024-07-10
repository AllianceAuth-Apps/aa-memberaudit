"""Shared ESI client for Member Audit."""

from esi.clients import EsiClientProvider

from memberaudit import __version__

esi = EsiClientProvider(app_info_text=f"aa-memberaudit v{__version__}")
