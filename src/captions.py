from __future__ import annotations

import random

from .models import AssetPlan, PlatformConfig


def build_caption(platform: PlatformConfig, rng: random.Random, plan_seed: str) -> str:
    del rng
    if not platform.caption_patterns:
        return ""
    seeded = random.Random(f"{plan_seed}:{platform.name}:{platform.daily_count}")
    return seeded.choice(platform.caption_patterns)


def metadata_for_plan(plan: AssetPlan) -> dict[str, str]:
    return {
        "asset_id": plan.asset_id,
        "hook_id": plan.hook.id,
        "subtitle_id": plan.subtitle.id,
        "image_id": plan.image_id,
        "platform": plan.platform,
    }
