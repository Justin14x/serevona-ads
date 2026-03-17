from __future__ import annotations

import unittest

from scripts.common.models import PendingUpload
from scripts.send_telegram_batch import _merge_batches, _selected_platforms, _summary_text


class TelegramBatchTests(unittest.TestCase):
    def test_merge_batches_deduplicates_same_reel_across_platforms(self) -> None:
        shared = PendingUpload(
            reel_id="reel-1",
            sequence_index=1,
            file_path="batch_001/1.mp4",
            platform_status_id="status-1",
            platform="instagram",
        )
        merged = _merge_batches(
            {
                "instagram": [shared],
                "youtube": [PendingUpload(**{**shared.__dict__, "platform": "youtube", "platform_status_id": "status-2"})],
                "tiktok": [],
            },
            ["instagram", "youtube"],
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].platforms, ["instagram", "youtube"])

    def test_summary_text_includes_platform_counts(self) -> None:
        payload = {
            "instagram": [
                PendingUpload("reel-1", 1, "batch_001/1.mp4", "a", "instagram"),
            ],
            "tiktok": [],
        }
        text = _summary_text(payload, _merge_batches(payload, ["instagram", "tiktok"]), ["instagram", "tiktok"])
        self.assertIn("Instagram: 1", text)
        self.assertIn("Unique reels: 1", text)
        self.assertNotIn("YouTube:", text)

    def test_selected_platforms_support_all_platforms(self) -> None:
        self.assertEqual(_selected_platforms("instagram,youtube,tiktok"), ["instagram", "youtube", "tiktok"])


if __name__ == "__main__":
    unittest.main()
