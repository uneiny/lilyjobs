from __future__ import annotations

import json
from pathlib import Path


def load_sites_config(config_path: Path) -> list[dict]:
    if not config_path.exists():
        return []

    with config_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("sites_config.json은 사이트 목록 배열이어야 합니다.")

    return data
