-- offsite_deals 命名迁移（安全、手动执行）。
-- slickdeals_deals 实际同时存放 Slickdeals 与 hip2save 数据，命名已不准确。
--
-- 生产迁移步骤（确认当前表还叫 slickdeals_deals 时，手动执行下面这行）：
-- alter table public.slickdeals_deals rename to offsite_deals;
--
-- 无法安全判断是否已重命名时，不要自动执行 rename。仅在确认后手动跑。
-- 重命名后建立/保留必要索引：

create index if not exists idx_offsite_deals_category_scraped_at
on public.offsite_deals(category, scraped_at);

create index if not exists idx_offsite_deals_source_scraped_at
on public.offsite_deals(source, scraped_at);

create unique index if not exists idx_offsite_deals_deal_id
on public.offsite_deals(deal_id);

-- 迁移完成后，把环境变量切换为：
--   OFFSITE_DEALS_TABLE=offsite_deals
-- 代码默认仍指向旧表 slickdeals_deals，未迁移前不受影响。
