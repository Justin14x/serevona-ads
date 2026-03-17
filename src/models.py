from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CreativeText:
    id: str
    text: str
    category: str
    enabled: bool
    weight: float = 1.0


@dataclass(frozen=True)
class PlatformConfig:
    name: str
    daily_count: int
    caption_patterns: list[str]
    reuse_across_platforms: bool = True
    enabled: bool = True


@dataclass(frozen=True)
class TemplateMap:
    template_id: str
    fields: dict[str, str]


@dataclass(frozen=True)
class AssetPlan:
    run_id: str
    asset_id: str
    platform: str
    sequence: int
    image_id: str
    image_path: Path
    hook: CreativeText
    subtitle: CreativeText
    caption: str


@dataclass
class RenderedAsset:
    plan: AssetPlan
    export_path: Path
    thumbnail_path: Path
    upload_status: dict[str, str] = field(default_factory=dict)
    upload_refs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeSettings:
    workspace: Path
    config_dir: Path
    assets_dir: Path
    outputs_dir: Path
    state_dir: Path
    run_id: str
    canva_mode: str
    same_pair_cooldown_days: int
    image_cooldown_days: int
    dry_run_uploads: bool
    sample: bool
    force: bool
    xlsx_source: Path | None
