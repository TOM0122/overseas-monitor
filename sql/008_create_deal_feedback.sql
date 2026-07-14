create table if not exists public.deal_feedback (
  id bigserial primary key,
  deal_id text not null,
  feedback_type text not null check (
    feedback_type in (
      'valid',
      'false_positive',
      'important',
      'ignore',
      'brand_candidate',
      'price_watch',
      'content_opportunity'
    )
  ),
  reason text,
  note text,
  created_by text,
  created_at timestamptz not null default now()
);

create index if not exists idx_deal_feedback_deal_id
on public.deal_feedback(deal_id);

create index if not exists idx_deal_feedback_type
on public.deal_feedback(feedback_type);

create index if not exists idx_deal_feedback_created_at
on public.deal_feedback(created_at desc);

-- MVP access model: Vercel Deployment Protection guards the UI, and all feedback
-- reads/writes run in Server Components or Server Actions with the service role.
alter table public.deal_feedback enable row level security;
revoke all on table public.deal_feedback from anon, authenticated;
revoke all on sequence public.deal_feedback_id_seq from anon, authenticated;
grant select, insert on table public.deal_feedback to service_role;
grant usage, select on sequence public.deal_feedback_id_seq to service_role;

comment on table public.deal_feedback is
'Manual deal review history from the Vercel operations console. Latest row is the current UI status.';
