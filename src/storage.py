from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import CreativeText, PlatformConfig, TemplateMap


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_hooks(config_dir: Path) -> list[CreativeText]:
    raw = load_json(config_dir / "hooks.json")
    return [CreativeText(**item) for item in raw if item.get("enabled", True)]


def load_subtitles(config_dir: Path) -> list[CreativeText]:
    raw = load_json(config_dir / "subtitles.json")
    return [CreativeText(**item) for item in raw if item.get("enabled", True)]


def load_platforms(config_dir: Path) -> list[PlatformConfig]:
    raw = load_json(config_dir / "platforms.json")
    return [
        PlatformConfig(name=name, **payload)
        for name, payload in raw.items()
        if payload.get("enabled", True)
    ]


def load_template_map(config_dir: Path) -> TemplateMap:
    raw = load_json(config_dir / "template_map.json")
    return TemplateMap(**raw)


def load_usage_log(state_dir: Path) -> dict[str, Any]:
    raw = load_json(state_dir / "usage_log.json")
    return {"assets": raw.get("assets", [])}


def load_run_history(state_dir: Path) -> dict[str, Any]:
    raw = load_json(state_dir / "run_history.json")
    return {"runs": raw.get("runs", [])}


def append_run_history(state_dir: Path, run_payload: dict[str, Any]) -> None:
    current = load_run_history(state_dir)
    current["runs"].append(run_payload)
    write_json(state_dir / "run_history.json", current)


def append_usage_records(state_dir: Path, usage_records: list[dict[str, Any]]) -> None:
    current = load_usage_log(state_dir)
    current["assets"].extend(usage_records)
    write_json(state_dir / "usage_log.json", current)
