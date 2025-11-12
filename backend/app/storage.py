from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import settings


def _project_dir(project_id: int) -> Path:
    base = Path(settings.data_dir) / f"project_{project_id}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_payload(project_id: int, name: str, payload: Any) -> Path:
    path = _project_dir(project_id) / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_payload(project_id: int, name: str) -> Any | None:
    path = _project_dir(project_id) / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
