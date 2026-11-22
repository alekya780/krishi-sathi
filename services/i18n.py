import json
from pathlib import Path

TEXT = json.loads((Path(__file__).resolve().parents[1] / "data/translations.json").read_text(encoding="utf-8"))


def translate(key: str, language: str, **values) -> str:
    return TEXT[key][language].format(**values)
