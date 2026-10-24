from pathlib import Path

import yaml

DIR = Path(__file__).resolve().parent.parent / "lenses"


def load(domain: str) -> dict:
    key = domain.lower().replace(" ", "_")
    path = DIR / f"{key}.yaml"
    if not path.exists():
        path = DIR / "generic.yaml"
    return yaml.safe_load(path.read_text())
