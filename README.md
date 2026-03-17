# Serevona Distribution Bot

Distribution-first bot for sequenced short-form reel delivery. Canva is treated as an offline content factory. Finished MP4 reels are ingested into Supabase Storage and Supabase Postgres, then delivered to Telegram in deterministic sequence order so you can post manually on every platform.

## Milestone 1

- Supabase schema for `reels` and `reel_platform_status`
- Ingestion script for local MP4 batches
- Sequential selection from the top per platform
- Telegram batch delivery for Instagram, YouTube, and TikTok
- GitHub Actions workflows for ingestion, scheduled uploads, and manual reset/retry

## Architecture

- Canva: manual/offline reel creation and export
- Supabase Storage: canonical MP4 storage in bucket `reels`
- Supabase Postgres: reel metadata, per-platform state, ordering, duplicate prevention
- GitHub Actions: scheduler and job runner
- Telegram delivery: treat successful send as `posted`

## Repository Layout

```text
.
├── .github/workflows/
│   ├── ingest_reels.yml
│   ├── retry_failed.yml
│   └── upload_reels.yml
├── imports/reels/
├── scripts/
│   ├── common/
│   ├── ingest_reels.py
│   ├── mark_status.py
│   ├── select_next_batch.py
│   ├── upload_instagram.py
│   ├── upload_platform.py
│   ├── upload_tiktok.py
│   └── upload_youtube.py
├── supabase/schema.sql
└── README.md
```

## Environment

Create a local `.env` in the repo root with:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

The scripts auto-load `.env` from the project root.

## Supabase Setup

1. Create a Storage bucket named `reels`.
2. Apply the SQL in [schema.sql](/Users/justinolaleye/Desktop/SerevonaMedia/supabase/schema.sql).
3. Confirm the service role key has Storage and Postgres access.

## Ingestion

Put exported Canva MP4 files into [imports/reels](/Users/justinolaleye/Desktop/SerevonaMedia/imports/reels), then run:

```bash
python scripts/ingest_reels.py --batch batch_001 --input ./imports/reels
```

What ingestion does:

- scans local MP4 files in sorted order
- computes a SHA-256 content hash from file bytes
- assigns the next `sequence_index`
- uploads each file to Supabase Storage
- inserts a row into `reels`
- inserts `pending` platform rows for instagram, tiktok, and youtube

To test without writing anything:

```bash
python scripts/ingest_reels.py --batch batch_001 --input ./imports/reels --dry-run
```

## Sequential Selection

Print the next pending reels per platform:

```bash
python scripts/select_next_batch.py
```

Batch limits are fixed:

- Instagram: 5
- YouTube: 5
- TikTok: 2

Selection is always:

- ordered by `sequence_index asc`
- filtered by `status = pending`
- independent per platform

## Telegram Delivery

Preview the next Telegram batch:

```bash
python scripts/send_telegram_batch.py --dry-run
```

Live Telegram send:

```bash
python scripts/send_telegram_batch.py
```

What it does:

- selects Instagram next 5, YouTube next 5, and TikTok next 2
- merges overlapping reels so duplicate files are sent once
- sends one summary message plus the video files to your Telegram chat
- marks the selected platform rows `posted` after successful Telegram delivery

## Manual Reset / Status Updates

Reset one reel/platform pair to `pending`:

```bash
python scripts/mark_status.py --reel-id <uuid> --platform instagram --reset
```

Mark one reel/platform pair explicitly:

```bash
python scripts/mark_status.py --reel-id <uuid> --platform instagram --status failed --error-message "API timeout"
```

## GitHub Actions

- [ingest_reels.yml](/Users/justinolaleye/Desktop/SerevonaMedia/.github/workflows/ingest_reels.yml): manual ingestion
- [upload_reels.yml](/Users/justinolaleye/Desktop/SerevonaMedia/.github/workflows/upload_reels.yml): daily 9:00 PM America/Chicago Telegram delivery
- [retry_failed.yml](/Users/justinolaleye/Desktop/SerevonaMedia/.github/workflows/retry_failed.yml): manual reset or status override

## Notes

- GitHub is not used for storing MP4 reels.
- Duplicate prevention is enforced by `content_hash` and `unique(reel_id, platform)`.
- A reel is sent to Telegram once per platform batch selection unless manually reset.
- Successful Telegram delivery is treated as final completion for platform state in this workflow.
- Legacy YouTube OAuth and uploader helpers remain in `scripts/` but are not part of the active workflow.
- The legacy Canva runtime generation code still exists in `src/`, but the active product path is now ingestion plus Supabase plus Telegram delivery.

## Tests

```bash
python3 -m unittest discover -s tests
```
