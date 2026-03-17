create extension if not exists pgcrypto;

create table if not exists public.reels (
  id uuid primary key default gen_random_uuid(),
  sequence_index integer unique not null,
  file_path text not null,
  batch_name text,
  header_text text,
  subtitle_text text,
  caption text,
  content_hash text unique not null,
  created_at timestamptz not null default now(),
  is_active boolean not null default true,
  last_error text
);

create table if not exists public.reel_platform_status (
  id uuid primary key default gen_random_uuid(),
  reel_id uuid not null references public.reels(id) on delete cascade,
  platform text not null check (platform in ('instagram', 'tiktok', 'youtube')),
  status text not null check (status in ('pending', 'queued', 'uploaded', 'posted', 'failed', 'skipped')),
  uploaded_at timestamptz,
  posted_at timestamptz,
  platform_post_id text,
  error_message text,
  attempt_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (reel_id, platform)
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists reel_platform_status_set_updated_at on public.reel_platform_status;
create trigger reel_platform_status_set_updated_at
before update on public.reel_platform_status
for each row execute function public.set_updated_at();
