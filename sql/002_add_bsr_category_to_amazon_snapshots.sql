alter table amazon_snapshots
add column if not exists bsr_category_id text,
add column if not exists bsr_category_name text;

create index if not exists idx_amazon_snapshots_bsr_category_asin_snapshot_at
on amazon_snapshots(bsr_category_id, asin, snapshot_at);
