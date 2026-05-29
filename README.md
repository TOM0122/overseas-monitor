# 海外推广数据监控 AI Agent

阶段一 MVP：每天抓取 Slickdeals 活跃 Deal、拉取 Keepa Amazon 快照、生成竞品日报，并推送到钉钉群。

## 技术栈

- Python 3.11+
- Slickdeals: `requests` + `BeautifulSoup`
- Amazon: Keepa API
- Database: Supabase PostgreSQL
- LLM: DeepSeek API or another OpenAI-compatible API
- Push: DingTalk custom robot webhook
- Deploy: Railway Cron

## 目录结构

```text
.
├── config/
│   ├── asin_list.txt
│   ├── brand_list.txt
│   └── keywords.txt
├── scrapers/
│   ├── hip2save_scraper.py
│   ├── keepa_fetcher.py
│   └── slickdeals_scraper.py
├── analysis/
│   └── analyzer.py
├── utils/
│   ├── db.py
│   ├── dingtalk.py
│   └── llm_client.py
├── prompts/
│   └── daily_report.md
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
pip install -r requirements.txt
```

3. 创建本地环境变量：

```bash
cp .env.example .env
```

然后填写 `.env` 中的 Supabase、Keepa、DeepSeek API、钉钉 Webhook 配置。

4. 在 Supabase SQL Editor 中创建数据表：

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
  posted_at timestamptz,
  scraped_at timestamptz default now()
);

create table amazon_snapshots (
  id bigserial primary key,
  asin text,
  brand text,
  title text,
  category text,
  price numeric,
  bsr int,
  rating numeric,
  review_count int,
  buy_box_price numeric,
  snapshot_at timestamptz default now()
);

create index on slickdeals_deals(category, scraped_at);
create index on slickdeals_deals(source, scraped_at);
create index on amazon_snapshots(asin, snapshot_at);
```

如果你的表已经按旧 schema 创建，执行一次迁移：

```sql
alter table slickdeals_deals
add column if not exists source text default 'slickdeals';

update slickdeals_deals
set source = 'slickdeals'
where source is null;

create index if not exists idx_slickdeals_source_scraped_at
on slickdeals_deals(source, scraped_at);
```

同样的 SQL 已保存为 `sql/001_add_source_to_slickdeals_deals.sql`。TODO：后续如确认多站点模型稳定，可考虑把表名从 `slickdeals_deals` 重命名为 `offsite_deals`。

## 配置文件格式

`config/keywords.txt`：

```text
portable fan | fan
handheld fan | fan
turbo fan | fan
rechargeable fan | fan
```

`config/asin_list.txt`：

```text
B0XXXXXXXX | fan
B0YYYYYYYY | hand_warmer
```

`config/brand_list.txt`：

```text
Aecooly
PlayHot
Gaiatop
SWEETFULL
Coolhill
Shark
Diveblues
```

## Slickdeals 爬虫

先用 dry-run 验证解析结果，不写入数据库：

```bash
python -m scrapers.slickdeals_scraper --limit 5 --dry-run
```

确认 `.env` 中 Supabase 配置可用后，正式写入数据库：

```bash
python -m scrapers.slickdeals_scraper --limit 20
```

如果 dry-run 返回空列表或遇到 403，保存返回页面用于排查：

```bash
python -m scrapers.slickdeals_scraper --limit 5 --dry-run --debug-html
```

调试文件会保存在 `debug/slickdeals/`，该目录不会提交到 Git。

## hip2save 爬虫

hip2save 使用同一份 `config/keywords.txt` 和 `config/brand_list.txt`，归一化写入 `slickdeals_deals` 表，并用 `source='hip2save'` 区分来源。

先 dry-run 并保存样本 HTML：

```bash
python -m scrapers.hip2save_scraper --limit 5 --dry-run --debug-html
```

确认解析结果后正式写库：

```bash
python -m scrapers.hip2save_scraper --limit 20
```

hip2save 是博客式折扣站，通常没有点赞数；抓不到的字段会写 `null`，不会用其它数字硬凑。

## Keepa 拉取

先在 `.env` 中配置：

```text
KEEPA_API_KEY=your_keepa_api_key
KEEPA_DOMAIN=US
KEEPA_STATS_DAYS=1
KEEPA_REQUEST_DELAY_SECONDS=3
KEEPA_FETCH_BUYBOX=true
```

`KEEPA_FETCH_BUYBOX=true` 会额外消耗 Keepa token，但可以得到 `buy_box_price`。如果 token 紧张，可以临时改成 `false`，此时 `buy_box_price` 可能为空。

验证 ASIN 拉取，不写数据库：

```bash
python -m scrapers.keepa_fetcher --check-key
```

如果 API key 正常，会输出 token 状态。然后再测试单个 ASIN：

```bash
python -m scrapers.keepa_fetcher --limit 1 --dry-run
```

正式写入 `amazon_snapshots`：

```bash
python -m scrapers.keepa_fetcher
```

## 分析与钉钉推送

先确认 `.env` 中已配置 Supabase、DeepSeek API、钉钉机器人：

```text
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=...
LLM_MODEL=deepseek-v4-flash
LLM_MAX_TOKENS=3000
LLM_TEMPERATURE=0.2
DINGTALK_WEBHOOK_URL=...
DINGTALK_WEBHOOK_SECRET=
TIMEZONE=Asia/Shanghai
ANALYSIS_TOP_DEALS_LIMIT=20
```

只拉取 Supabase 数据并打印整理后的报告输入，不调用 LLM、不推送：

```bash
python -m analysis.analyzer --dry-run
```

调用 DeepSeek 生成报告，但不推送钉钉：

```bash
python -m analysis.analyzer --no-push
```

正式生成并推送钉钉：

```bash
python -m analysis.analyzer
```

## Railway 部署要点

`main.py` 是生产入口，默认按顺序执行：

1. Slickdeals 爬取并写入 `slickdeals_deals`
2. hip2save 爬取并写入 `slickdeals_deals`
3. Keepa 拉取并写入 `amazon_snapshots`
4. 读取当天数据，生成日报，并推送到钉钉

本地完整 dry-run：

```bash
python main.py --dry-run
```

本地正式跑完整链路：

```bash
python main.py
```

可选排查命令：

```bash
python main.py --skip-analysis
python main.py --skip-slickdeals --skip-hip2save --skip-keepa --dry-run
python main.py --slickdeals-limit 5 --dry-run
```

Railway 官方文档说明，Cron Job 会按服务配置里的 crontab 表达式执行该服务的 start command，并且任务应执行完成后退出；本项目的 `python main.py` 符合这个模式。

### Railway 操作步骤

1. 将项目推送到 GitHub。不要提交 `.env`，真实密钥只放 Railway Variables。
2. 打开 Railway，创建新项目，选择 `Deploy from GitHub repo`。
3. 选择这个仓库，Railway 会根据 `requirements.txt` 安装 Python 依赖。
4. 在服务的 Variables 中逐项添加 `.env.example` 里的生产变量：

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
KEEPA_API_KEY
KEEPA_DOMAIN
KEEPA_STATS_DAYS
KEEPA_REQUEST_DELAY_SECONDS
KEEPA_FETCH_BUYBOX
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
LLM_MAX_TOKENS
LLM_TEMPERATURE
DINGTALK_WEBHOOK_URL
DINGTALK_WEBHOOK_SECRET
LOG_LEVEL
TIMEZONE
ANALYSIS_TOP_DEALS_LIMIT
```

5. 确认 Deploy 设置：
   - Start Command：`python main.py`
   - Cron Schedule：`0 1 * * *`
   - 对应北京时间每天 09:00，因为 Railway Cron 使用 UTC 表达。

6. 首次部署后，在 Railway Logs 里确认三步都有类似日志：

```text
Starting step: slickdeals_scraper
Starting step: hip2save_scraper
Starting step: keepa_fetcher
Starting step: daily_analyzer
Pipeline summary: ...
```

7. 如果某一步失败，`main.py` 会记录错误并继续执行后续步骤。先看 Railway Logs，常见问题是环境变量缺失、Slickdeals 返回 403、Keepa token 不足、钉钉机器人安全设置不匹配。

仓库里已经提供 `railway.json`：

```json
{
  "deploy": {
    "startCommand": "python main.py",
    "cronSchedule": "0 1 * * *"
  }
}
```

如果你想在 Railway 控制台手动调整时间，以控制台设置为准。

## 当前阶段

阶段一 MVP 已包含 Slickdeals、Keepa、DeepSeek 分析、钉钉推送和 Railway Cron 入口。
