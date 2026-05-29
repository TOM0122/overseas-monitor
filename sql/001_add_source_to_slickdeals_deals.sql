alter table slickdeals_deals
add column if not exists source text default 'slickdeals';

update slickdeals_deals
set source = 'slickdeals'
where source is null;

create index if not exists idx_slickdeals_source_scraped_at
on slickdeals_deals(source, scraped_at);
