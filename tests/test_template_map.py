from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.storage import load_template_map


class TemplateMapTests(unittest.TestCase):
    def test_load_template_map_uses_brand_template_and_field_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir)
            (config_dir / "template_map.json").write_text(
                (
                    '{'
                    '"template_id":"EAHEFZ9SogE",'
                    '"fields":{"background_image":"background_image:image","header_text":"header_text","subtitle_text":"subtitle_text"}'
                    '}'
                ),
                encoding="utf-8",
            )

            template_map = load_template_map(config_dir)

            self.assertEqual(template_map.template_id, "EAHEFZ9SogE")
            self.assertEqual(template_map.fields["background_image"], "background_image:image")


if __name__ == "__main__":
    unittest.main()
