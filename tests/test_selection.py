from __future__ import annotations

import unittest

from scripts.common.models import BATCH_LIMITS


class SelectionContractTests(unittest.TestCase):
    def test_platform_batch_limits_match_spec(self) -> None:
        self.assertEqual(BATCH_LIMITS["instagram"], 5)
        self.assertEqual(BATCH_LIMITS["youtube"], 5)
        self.assertEqual(BATCH_LIMITS["tiktok"], 2)


if __name__ == "__main__":
    unittest.main()
