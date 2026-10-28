-- Run once in the Supabase SQL editor.
-- Append-only, versioned prompt storage: every edit is a new row.
create table if not exists prompt_versions (
  id             bigint generated always as identity primary key,
  prompt_name    text        not null default 'reply',
  version        integer     not null,
  content        text        not null,
  source         text        not null check (source in ('seed', 'auto', 'manual', 'rollback')),
  change_summary text,
  metadata       jsonb       not null default '{}'::jsonb,
  created_at     timestamptz not null default now(),
  unique (prompt_name, version)
);

-- The server uses the service_role key, which bypasses RLS. Enabling RLS
-- with no policies blocks the public anon key from reading or writing.
alter table prompt_versions enable row level security;
