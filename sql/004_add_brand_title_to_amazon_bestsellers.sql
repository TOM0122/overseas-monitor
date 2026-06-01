alter table public.amazon_bestsellers
    add column if not exists brand text,
    add column if not exists title text;
