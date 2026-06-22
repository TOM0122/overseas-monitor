# 海外推广数据监控 AI Agent

当前版本是站外推广监控 Agent：每天抓取 Slickdeals / hip2save 的活跃折扣 Deal，整理站外竞品动态，调用 DeepSeek（或其它 OpenAI-compatible API）生成中文日报，并推送到钉钉群。

已停用：Keepa、Amazon snapshots、Amazon Best Sellers / Top30 / BSR 监测。历史 Supabase 表和 SQL 迁移保留，但本 Agent 不再写入或展示这些站内数据。

## 技术栈

- Python 3.11+
- Slickdeals / hip2save: `requests` + `BeautifulSoup`
- Database: Supabase PostgreSQL
- LLM: DeepSeek API or another OpenAI-compatible API
- Push: DingTalk custom robot webhook
- Deploy: Railway Cron

## 目录结构

```text
.
├── config/
│   ├── brand_list.txt
│   └── keywords.txt
├── scrapers/
│   ├── hip2save_scraper.py
│   └── slickdeals_scraper.py
├── analysis/
│   └── analyzer.py
├── utils/
│   ├── data_quality.py
│   ├── db.py
│   ├── dingtalk.py
│   └── llm_client.py
├── prompts/
│   └── daily_report.md
├── sql/
├── tests/
├── main.py
├── railway.json
├── requirements.txt
└── .env.example
```

## 本地启动

1. 创建虚拟环境：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

2. 安装依赖：

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-dev.txt
```

3. 创建本地环境变量：

```bash
cp .env.example .env
```

然后填写 `.env` 中的 Supabase、DeepSeek API、钉钉 Webhook 配置。

4. 运行测试：

```bash
.venv/bin/python -m pytest
```

## Supabase Schema

当前生产写入只依赖 `slickdeals_deals` 表。表名沿用历史命名，实际已承载 Slickdeals 和 hip2save 两个站外来源；后续可考虑重命名为 `offsite_deals`。

```sql
create table slickdeals_deals (
  id bigserial primary key,
  source text default 'slickdeals',
  deal_id text unique,
  title text,
  brand text,
  category text,
  price numeric,
  original_price numeric,
  discount_pct numeric,
  url text,
  thumbs_up int,
  comments_count int,
  is_frontpage boolean,
  posted_at timestamptz,
  scraped_at timestamptz default now()
);

create index on slickdeals_deals(category, scraped_at);
create index on slickdeals_deals(source, scraped_at);
```

如果你的表来自旧版本，请确认至少执行过这些迁移：

```sql
alter table slickdeals_deals
add column if not exists source text default 'slickdeals';

update slickdeals_deals
set source = 'slickdeals'
where source is null;

create index if not exists idx_slickdeals_source_scraped_at
on slickdeals_deals(source, scraped_at);

alter table public.slickdeals_deals
add column if not exists is_frontpage boolean;
```

对应 SQL 已保存在 `sql/001_add_source_to_slickdeals_deals.sql` 和 `sql/005_add_is_frontpage_to_slickdeals_deals.sql`。

历史表 `amazon_snapshots`、`amazon_bestsellers` 及相关 SQL 迁移保留在项目中，仅供历史数据查询或未来恢复使用；当前 pipeline 不写入、不读取、不进入日报。

## 配置文件格式

`config/keywords.txt`：

```text
portable fan | fan
handheld fan | fan
turbo fan | fan
rechargeable fan | fan
```

`config/brand_list.txt` 是重点监控品牌列表，也是日报主要竞品表的品牌范围：

```text
Aecooly
PlayHot
Gaiatop
SWEETFULL
Coolhill
Shark
Diveblues
```

## 爬虫

Slickdeals dry-run，不写数据库：

```bash
.venv/bin/python -m scrapers.slickdeals_scraper --limit 5 --dry-run --debug-html
```

hip2save dry-run，不写数据库：

```bash
.venv/bin/python -m scrapers.hip2save_scraper --limit 5 --dry-run --debug-html
```

确认解析结果后正式写库：

```bash
.venv/bin/python -m scrapers.slickdeals_scraper --limit 20
.venv/bin/python -m scrapers.hip2save_scraper --limit 20
```

调试 HTML 会保存到 `debug/slickdeals/` 和 `debug/hip2save/`，不会提交到 Git。

站外噪音过滤规则：

- `fan` 类目会排除玩具/一元区/食品合集语境，如 `bullseye`、`playground`、`blaster`、`bubble fan`、`peeps`、`cupcake`、`hostess`。
- 排除粉丝/受众语境，如 `Dunkin' Fans`、`Soccer Fans`。
- 排除家用大风扇，如 `ceiling fan`、`tower fan`、`pedestal fan`、`box fan`。
- Analyzer 出报告前会再次做类目相关性复核，已入库的历史噪音也会被即时滤除。
- 站外报告会丢弃价格低于 `ANALYSIS_MIN_OFFSITE_PRICE`（默认 `$5`）的 Deal，价格缺失的 Deal 不会因此被丢弃。

## 分析与钉钉推送

日报固定四段：

1. 总览
2. 站外每日发现
3. 建议
4. 注意

只拉取 Supabase 数据并打印整理后的报告输入，不调用 LLM、不推送：

```bash
.venv/bin/python -m analysis.analyzer --dry-run
```

调用 DeepSeek 生成报告，但不推送钉钉：

```bash
.venv/bin/python -m analysis.analyzer --no-push
```

日报推送前会自动归一化钉钉 Markdown 排版，并按 `DINGTALK_MARKDOWN_MAX_BYTES` 做 UTF-8 字节截断保护；内容过长时只截断消息，不会因为超长导致整条推送失败。

## 环境变量

`.env.example` 是完整样板。生产环境在 Railway Variables 中配置同名变量。

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY

LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
LLM_MAX_TOKENS
LLM_TEMPERATURE

DINGTALK_WEBHOOK_URL
DINGTALK_WEBHOOK_SECRET
DINGTALK_MARKDOWN_MAX_BYTES

LOG_LEVEL
TIMEZONE
SCRAPER_MAX_RETRIES
SCRAPER_BACKOFF_SECONDS
DATA_QUALITY_DROP_RATIO

ANALYSIS_TOP_DEALS_LIMIT
ANALYSIS_OFFSITE_CATEGORY
ANALYSIS_OFFSITE_CATEGORY_LABEL
ANALYSIS_FOCUS_BRAND
ANALYSIS_MAX_REASONABLE_PRICE
ANALYSIS_MIN_OFFSITE_PRICE
SLICKDEALS_MAX_POST_AGE_DAYS
```

`ANALYSIS_OFFSITE_CATEGORY_LABEL` 是日报展示用的品类名；`ANALYSIS_FOCUS_BRAND` 是日报优先展开的自有/重点品牌，需与 `config/brand_list.txt` 中的写法一致。

## Railway 部署

`main.py` 是生产入口，默认按顺序执行：

1. Slickdeals 爬取并写入 `slickdeals_deals`
2. hip2save 爬取并写入 `slickdeals_deals`
3. 读取当天站外数据，生成四段日报，并推送到钉钉

本地完整 dry-run：

```bash
.venv/bin/python main.py --dry-run
```

排查命令：

```bash
.venv/bin/python main.py --skip-analysis --dry-run
.venv/bin/python main.py --skip-slickdeals --skip-hip2save --dry-run
.venv/bin/python main.py --slickdeals-limit 5 --dry-run
```

仓库里提供 `railway.json`：

```json
{
  "deploy": {
    "startCommand": "python main.py",
    "cronSchedule": "50 0 * * *"
  }
}
```

Railway Cron 使用 UTC 表达式。`50 0 * * *` 对应北京时间每天 08:50，预留运行时间，目标是在北京时间 09:00 前后收到日报。

首次部署后，在 Railway Logs 里确认三步都有类似日志：

```text
Starting step: slickdeals_scraper
Starting step: hip2save_scraper
Starting step: daily_analyzer
Pipeline summary: ...
```

如果某一步失败，`main.py` 会记录错误并继续执行后续步骤；非 dry-run 的失败步骤会触发钉钉告警，并在有步骤失败时以非零退出码结束，让 Railway 标记失败。

## 验证命令

改动代码后至少运行：

```bash
.venv/bin/python -m compileall main.py analysis scrapers utils
.venv/bin/python -m pytest -q
```

涉及 scraper / analyzer 的改动，再运行对应 dry-run：

```bash
.venv/bin/python -m analysis.analyzer --dry-run
.venv/bin/python main.py --dry-run
```
