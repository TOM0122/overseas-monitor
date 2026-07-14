# 海外推广数据监控 AI Agent

当前版本是站外推广监控 Agent：每天抓取 Slickdeals / hip2save 的活跃折扣 Deal，整理站外竞品动态，调用 DeepSeek（或其它 OpenAI-compatible API）生成中文日报，并推送到钉钉群。

## Web UI / Feedback Console

仓库中的 `web/` 是独立的 Next.js 运营控制台，由 Vercel 部署；Python Agent 与 Railway Cron 入口保持不变。Web UI 读取 Supabase 中的 `agent_runs`、站外 Deal 表和 `deal_feedback`，提供 Dashboard、运行详情、Deal 人工复核及报告历史。

第一版使用 Vercel Deployment Protection 保护访问。Feedback 写入经过 Next.js Server Action，`SUPABASE_SERVICE_ROLE_KEY` 只存在于服务端，不暴露给浏览器。第一版不支持在线修改 keywords / brand_list / category rules，也不支持手动重跑 Agent、重新生成报告或重新推送钉钉。

初始化与构建：

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
npm run build
```

部署前在 Supabase SQL Editor 执行 `sql/008_create_deal_feedback.sql`，再按 [web/README.md](web/README.md) 配置 Vercel Root Directory、环境变量与 Deployment Protection。

已停用：Keepa、Amazon snapshots、Amazon Best Sellers / Top30 / BSR 监测。历史 Supabase 表和 SQL 迁移保留，但本 Agent 不再写入或展示这些站内数据。

## 定位与每日运行流程

这是一个 **Offsite Deal Monitor / LLM-assisted competitor report agent**，不是站内 Amazon / Keepa 监控。每次运行是一个可追踪的 **Agent Run**：

1. scrape Slickdeals → 2. scrape hip2save → 3. write offsite deals（`offsite_deals`，旧库仍为 `slickdeals_deals`）
4. build deterministic insights（`analysis/insights.py`，规则先算好 suggestion candidates）
5. call LLM（`utils/llm_client.py`，记录耗时/usage，失败重试）
6. validate report（`analysis/report_validator.py`：四段结构、主标题、链接白名单、禁用站内关键词、幻觉句式）
7. 校验不过 → 纠正重试一次 → 仍失败则 deterministic **fallback report**（`analysis/fallback_report.py`，绝不让当天无报告）
8. push DingTalk（`send_markdown` 返回 ok / errcode / errmsg / truncated / bytes）
9. record agent run（`utils/run_tracker.py` → `agent_runs` 表：step 结果/耗时、数据量、质量告警、LLM 信息、推送结果、状态）

某个 scraper 失败不阻断其它步骤；非 dry-run 且有失败步骤时最终非零退出。dry-run 不写库、不推钉钉、不记 agent run。

### 数据库表

- `offsite_deals`（站外 Deal，Slickdeals + hip2save 共用，`source` 区分）。**旧命名 `slickdeals_deals` 仍是默认**，执行 `sql/008_rename_slickdeals_to_offsite_deals.sql` 后把 `OFFSITE_DEALS_TABLE` 改为 `offsite_deals` 即可切换（代码有兼容 wrapper）。
- `agent_runs`（每次运行记录，`sql/007`）。
- `deal_feedback`（Web UI 人工复核历史，`sql/008_create_deal_feedback.sql`；RLS + server-only service role）。
- legacy `amazon_snapshots` / `amazon_bestsellers`：保留但已停用。

### 关键新增环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `OFFSITE_DEALS_TABLE` | `slickdeals_deals` | 站外 Deal 表名；迁移后改 `offsite_deals` |
| `SCRAPER_MAX_RUNTIME_SECONDS` | `600` | 单 source 运行预算，超出返回 partial 不崩溃 |
| `HIP2SAVE_MAX_DETAIL_PAGES_PER_KEYWORD` | `20` | hip2save 每关键词详情页上限 |
| `HIP2SAVE_DETAIL_SLEEP_MIN/MAX_SECONDS` | `2` / `3` | 详情页抓取间隔 |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` | `60` / `1` | LLM 请求超时与重试次数 |
| `DINGTALK_MARKDOWN_MAX_BYTES` | `19000` | 钉钉 markdown 字节上限（超出截断）|
| `DATA_QUALITY_MIN_SAMPLE` | `10` | 比例型质量告警的最小样本量（防低流量误报）|
| `DATA_QUALITY_UNKNOWN_BRAND_RATIO` / `NULL_PRICE_RATIO` / `DUP_RATIO` / `TITLE_UNIQUE_MIN_RATIO` | `0.85` / `0.7` / `0.3` / `0.5` | 各质量指标阈值 |

数据质量告警（volume 骤降 + unknown 品牌比例 + 价格缺失比例 + 重复 Deal 比例 + source 新鲜度 + 标题相似度）为 deterministic，warn-only，复用现有钉钉告警通道，写入 `agent_runs.quality_alerts`。类目相关性规则外置于 `config/category_rules.toml`（缺失时回退内置默认）。

## 本地开发

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

python -m compileall main.py analysis scrapers utils tests
python -m pytest -q

python -m analysis.analyzer --dry-run   # 打印 payload，不调 LLM
python main.py --dry-run                # 全流程 dry-run，不写库/不推送/不记 run
```

CI：`.github/workflows/ci.yml` 在 push / PR 时跑 compile + pytest（3.11）。测试全程 mock 外部服务，不访问真实网络。

### 生产部署与排查

- Railway Cron：`cronSchedule` 用 UTC；`50 0 * * *` = 北京 08:50。见 `railway.json`。
- 检查运行历史：查 Supabase `agent_runs`（按 `started_at desc`），看 `status` / `step_results` / `quality_alerts` / `push_result` / `error_summary`。
- 排查某 source 抓取失败：看当天 `agent_runs.step_results` 里对应 step 的 `error` 与 `partial`，或 Railway 日志中 `run=<id>` 前缀。
- 安全：不要提交真实 `.env`；密钥在 Railway Variables 配置；Supabase service role key 权限较大，勿外泄。

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
├── web/                    # Next.js + Supabase 运营控制台，Vercel 部署
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
