create table if not exists agent_runs (
  id uuid primary key default gen_random_uuid(),
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  status text not null default 'running',
  trigger_type text default 'cron',
  timezone text,
  report_date date,
  step_results jsonb default '[]'::jsonb,
  source_counts jsonb default '{}'::jsonb,
  quality_alerts jsonb default '[]'::jsonb,
  llm_info jsonb default '{}'::jsonb,
  report_markdown text,
  push_result jsonb default '{}'::jsonb,
  error_summary text,
  created_at timestamptz not null default now()
);

create index if not exists idx_agent_runs_started_at on agent_runs(started_at desc);
create index if not exists idx_agent_runs_status on agent_runs(status);
create index if not exists idx_agent_runs_report_date on agent_runs(report_date);
