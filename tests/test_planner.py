from __future__ import annotations

import unittest
from pathlib import Path

from src.models import CreativeText, PlatformConfig, RuntimeSettings
from src.planner import build_daily_plan


class PlannerTests(unittest.TestCase):
    def test_planner_avoids_recent_pairs_and_duplicate_images_within_batch(self) -> None:
        workspace = Path("/tmp/serevona-test")
        settings = RuntimeSettings(
            workspace=workspace,
            config_dir=workspace / "config",
            assets_dir=workspace / "assets",
            outputs_dir=workspace / "outputs",
            state_dir=workspace / "state",
            run_id="2026-03-12_daily",
            canva_mode="mock",
            same_pair_cooldown_days=7,
            image_cooldown_days=3,
            dry_run_uploads=True,
            sample=True,
            force=False,
            xlsx_source=None,
        )
        hooks = [
            CreativeText(id="hook_1", text="hook 1", category="relief", enabled=True, weight=1.0),
            CreativeText(id="hook_2", text="hook 2", category="relief", enabled=True, weight=1.0),
        ]
        subtitles = [
            CreativeText(id="sub_1", text="sub 1", category="comment", enabled=True, weight=1.0),
            CreativeText(id="sub_2", text="sub 2", category="comment", enabled=True, weight=1.0),
        ]
        platforms = [PlatformConfig(name="instagram", daily_count=2, caption_patterns=["a"], enabled=True)]
        usage_log = {
            "assets": [
                {
                    "hook_id": "hook_1",
                    "subtitle_id": "sub_1",
                    "image_id": "sample_001.jpg",
                    "created_at": "2026-03-10T06:00:00+00:00",
                }
            ]
        }

        plan = build_daily_plan(settings, hooks, subtitles, platforms, usage_log)

        self.assertEqual(len(plan), 2)
        self.assertNotEqual((plan[0].hook.id, plan[0].subtitle.id), ("hook_1", "sub_1"))
        self.assertNotEqual(plan[0].image_id, plan[1].image_id)


if __name__ == "__main__":
    unittest.main()
