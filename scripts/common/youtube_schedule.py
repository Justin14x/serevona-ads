from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


YOUTUBE_TIMEZONE = "America/Chicago"
YOUTUBE_PUBLISH_HOURS = (8, 10, 12, 14, 16)
YOUTUBE_TITLE = 'escape and relax on the "Serevona" app 😞 #asmr #rain #meditate'
YOUTUBE_DESCRIPTION = """Escape into immersive cinematic worlds.
Download the app on the iOS store for more: Serevona.
🌧 Sleep
🌌 Focus
🧘 Meditate

#shorts"""


def next_publish_slots(
    count: int,
    *,
    now: datetime | None = None,
    timezone_name: str = YOUTUBE_TIMEZONE,
    hours: tuple[int, ...] = YOUTUBE_PUBLISH_HOURS,
) -> list[datetime]:
    if count > len(hours):
        raise ValueError(f"Only {len(hours)} YouTube publish slots are configured")

    tz = ZoneInfo(timezone_name)
    current = now.astimezone(tz) if now else datetime.now(tz)
    target_date = current.date() + timedelta(days=1)
    return [
        datetime.combine(target_date, time(hour=hour, minute=0), tzinfo=tz)
        for hour in hours[:count]
    ]


def youtube_publish_at_iso(slot: datetime) -> str:
    return slot.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
