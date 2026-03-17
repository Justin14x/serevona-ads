from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.main import execute_batch
from src.models import RuntimeSettings


class MainBatchTests(unittest.TestCase):
    def test_execute_batch_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            (workspace / "config").mkdir()
            (workspace / "assets" / "images").mkdir(parents=True)
            (workspace / "outputs").mkdir()
            (workspace / "state").mkdir()

            (workspace / "config" / "hooks.json").write_text(
                '[{"id":"hook_1","text":"hook 1","category":"relief","enabled":true,"weight":1.0}]',
                encoding="utf-8",
            )
            (workspace / "config" / "subtitles.json").write_text(
                '[{"id":"sub_1","text":"sub 1","category":"comment","enabled":true,"weight":1.0}]',
                encoding="utf-8",
            )
            (workspace / "config" / "platforms.json").write_text(
                '{"instagram":{"daily_count":1,"caption_patterns":["caption"],"enabled":true}}',
                encoding="utf-8",
            )
            (workspace / "config" / "template_map.json").write_text(
                '{"template_id":"CANVA_TEMPLATE_ID","fields":{"background_image":"bg","header_text":"h","subtitle_text":"s"}}',
                encoding="utf-8",
            )
            (workspace / "state" / "usage_log.json").write_text('{"assets":[]}', encoding="utf-8")
            (workspace / "state" / "run_history.json").write_text('{"runs":[]}', encoding="utf-8")

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

            summary = execute_batch(settings)

            self.assertEqual(summary["generated_count"], 1)
            self.assertTrue((workspace / "outputs" / "2026-03-12_daily_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
