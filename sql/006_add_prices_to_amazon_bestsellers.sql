alter table public.amazon_bestsellers
    add column if not exists price numeric,
    add column if not exists buy_box_price numeric,
    add column if not exists price_source text;
