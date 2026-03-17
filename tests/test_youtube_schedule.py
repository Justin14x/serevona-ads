from __future__ import annotations

from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

from scripts.common.youtube_schedule import (
    YOUTUBE_DESCRIPTION,
    YOUTUBE_TITLE,
    next_publish_slots,
    youtube_publish_at_iso,
)


class YoutubeScheduleTests(unittest.TestCase):
    def test_next_publish_slots_targets_next_day_in_chicago(self) -> None:
        now = datetime(2026, 3, 17, 21, 0, tzinfo=ZoneInfo("America/Chicago"))
        slots = next_publish_slots(5, now=now)
        self.assertEqual([slot.hour for slot in slots], [8, 10, 12, 14, 16])
        self.assertTrue(all(slot.date().isoformat() == "2026-03-18" for slot in slots))

    def test_publish_at_iso_converts_to_utc(self) -> None:
        slot = datetime(2026, 3, 18, 8, 0, tzinfo=ZoneInfo("America/Chicago"))
        self.assertEqual(youtube_publish_at_iso(slot), "2026-03-18T13:00:00Z")

    def test_metadata_constants_match_contract(self) -> None:
        self.assertEqual(YOUTUBE_TITLE, 'escape and relax on the "Serevona" app 😞 #asmr #rain #meditate')
        self.assertIn("#shorts", YOUTUBE_DESCRIPTION)


if __name__ == "__main__":
    unittest.main()
