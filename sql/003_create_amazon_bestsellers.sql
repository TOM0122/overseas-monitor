create table if not exists amazon_bestsellers (
  id bigserial primary key,
  category_id text not null,
  category_name text,
  rank int not null,
  asin text not null,
  is_tracked boolean default false,
  brand text,
  title text,
  snapshot_date date not null,
  snapshot_at timestamptz default now(),
  unique(category_id, asin, snapshot_date)
);

create index if not exists idx_amazon_bestsellers_category_snapshot_rank
on amazon_bestsellers(category_id, snapshot_at, rank);

create index if not exists idx_amazon_bestsellers_asin_snapshot
on amazon_bestsellers(asin, snapshot_at);
