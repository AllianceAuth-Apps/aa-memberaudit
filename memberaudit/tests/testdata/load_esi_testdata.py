import json
from pathlib import Path


def _load_from_file():
    path = Path(__file__).parent / "esi_testdata.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


esi_testdata = _load_from_file()
