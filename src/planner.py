from __future__ import annotations

import random
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .captions import build_caption
from .models import AssetPlan, CreativeText, PlatformConfig, RuntimeSettings


def _weighted_pick(
    rng: random.Random,
    items: list[CreativeText],
    penalties: Counter[str] | None = None,
) -> CreativeText:
    penalties = penalties or Counter()
    weights: list[float] = []
    for item in items:
        penalty = penalties.get(item.id, 0)
        weights.append(max(0.05, item.weight / (1 + penalty)))
    return rng.choices(items, weights=weights, k=1)[0]


def _parse_created_at(raw: str) -> date | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc).date()
    except ValueError:
        return None


def _recent_pairs(usage_assets: list[dict], run_date: date, cooldown_days: int) -> set[tuple[str, str]]:
    cutoff = run_date - timedelta(days=cooldown_days)
    pairs: set[tuple[str, str]] = set()
    for asset in usage_assets:
        created = _parse_created_at(asset.get("created_at", ""))
        if created and created >= cutoff:
            pairs.add((asset["hook_id"], asset["subtitle_id"]))
    return pairs


def _recent_images(usage_assets: list[dict], run_date: date, cooldown_days: int) -> Counter[str]:
    cutoff = run_date - timedelta(days=cooldown_days)
    images: Counter[str] = Counter()
    for asset in usage_assets:
        created = _parse_created_at(asset.get("created_at", ""))
        if created and created >= cutoff:
            images[asset["image_id"]] += 1
    return images


def discover_images(assets_dir: Path, sample: bool) -> list[Path]:
    image_dir = assets_dir / "images"
    if sample:
        image_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        path for path in sorted(image_dir.iterdir())
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    if paths:
        return paths
    if sample:
        return [image_dir / f"sample_{idx:03d}.jpg" for idx in range(1, 31)]
    raise FileNotFoundError(f"No images found in {image_dir}")


def build_daily_plan(
    settings: RuntimeSettings,
    hooks: list[CreativeText],
    subtitles: list[CreativeText],
    platforms: list[PlatformConfig],
    usage_log: dict,
) -> list[AssetPlan]:
    rng = random.Random(settings.run_id)
    run_date = datetime.strptime(settings.run_id.split("_")[0], "%Y-%m-%d").date()
    images = discover_images(settings.assets_dir, settings.sample)
    recent_pairs = _recent_pairs(usage_log["assets"], run_date, settings.same_pair_cooldown_days)
    recent_image_counts = _recent_images(usage_log["assets"], run_date, settings.image_cooldown_days)
    batch_image_ids: set[str] = set()
    pair_penalties = Counter(asset["hook_id"] for asset in usage_log["assets"])
    subtitle_penalties = Counter(asset["subtitle_id"] for asset in usage_log["assets"])

    plans: list[AssetPlan] = []
    for platform in platforms:
        for sequence in range(1, platform.daily_count + 1):
            max_attempts = max(40, len(hooks) * len(subtitles))
            selected: AssetPlan | None = None
            for allow_recent_pairs in (False, True):
                for _ in range(max_attempts):
                    hook = _weighted_pick(rng, hooks, pair_penalties)
                    subtitle = _weighted_pick(rng, subtitles, subtitle_penalties)
                    pair = (hook.id, subtitle.id)
                    if not allow_recent_pairs and pair in recent_pairs:
                        continue

                    image_candidates = [path for path in images if path.name not in batch_image_ids]
                    if not image_candidates:
                        image_candidates = images
                    image = min(
                        image_candidates,
                        key=lambda candidate: (recent_image_counts.get(candidate.name, 0), rng.random()),
                    )

                    asset_id = f"{platform.name}_{settings.run_id}_{sequence:03d}"
                    selected = AssetPlan(
                        run_id=settings.run_id,
                        asset_id=asset_id,
                        platform=platform.name,
                        sequence=sequence,
                        image_id=image.name,
                        image_path=image,
                        hook=hook,
                        subtitle=subtitle,
                        caption=build_caption(platform, rng, asset_id),
                    )
                    recent_pairs.add(pair)
                    batch_image_ids.add(image.name)
                    recent_image_counts[image.name] += 1
                    break
                if selected is not None:
                    break
            if selected is None:
                raise RuntimeError(f"Unable to produce a valid plan for {platform.name} item {sequence}")
            plans.append(selected)
    return plans
