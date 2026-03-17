from __future__ import annotations

import unittest
from pathlib import Path

from src.canva_client import _build_autofill_payload
from src.models import AssetPlan, CreativeText, TemplateMap


class CanvaClientTests(unittest.TestCase):
    def test_build_autofill_payload_uses_canva_dataset_keys(self) -> None:
        plan = AssetPlan(
            run_id="2026-03-16_daily",
            asset_id="instagram_2026-03-16_daily_001",
            platform="instagram",
            sequence=1,
            image_id="rain_001.jpg",
            image_path=Path("assets/images/rain_001.jpg"),
            hook=CreativeText(id="hook_1", text="header", category="relief", enabled=True),
            subtitle=CreativeText(id="sub_1", text="subtitle", category="comment", enabled=True),
            caption="caption",
        )
        template_map = TemplateMap(
            template_id="EAHEFZ9SogE",
            fields={
                "background_image": "background_image:image",
                "header_text": "header_text",
                "subtitle_text": "subtitle_text",
            },
        )

        payload = _build_autofill_payload(plan, template_map, image_asset_ref="asset_123")

        self.assertEqual(payload["brand_template_id"], "EAHEFZ9SogE")
        self.assertEqual(payload["data"]["background_image:image"]["asset_id"], "asset_123")
        self.assertEqual(payload["data"]["header_text"], "header")
        self.assertEqual(payload["data"]["subtitle_text"], "subtitle")


if __name__ == "__main__":
    unittest.main()
