alter table public.slickdeals_deals
    add column if not exists is_frontpage boolean;
