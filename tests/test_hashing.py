from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.common.hashing import sha256_file


class HashingTests(unittest.TestCase):
    def test_sha256_file_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "reel.mp4"
            path.write_bytes(b"reel-bytes")
            self.assertEqual(sha256_file(path), sha256_file(path))


if __name__ == "__main__":
    unittest.main()
