# Overseas Monitor Web Console

`web/` 是海外推广竞品监控 Agent 的中文运营控制台。Python Agent 继续由 Railway Cron 运行；本项目只读取 Supabase 数据、展示运行和报告，并通过 Server Action 写入 Deal Feedback。

## 页面

- `/`：今日运行状态、核心指标、最近运行、重点 Deal。
- `/runs`、`/runs/[id]`：运行列表与 JSON 字段结构化详情。
- `/deals`：Deal 筛选、原链接、复制链接、人工 Feedback。
- `/reports`、`/reports/[id]`：报告历史、Markdown 展示与复制。

第一版不提供配置修改、手动重跑 Agent、重新生成报告或重新推送钉钉。

## 本地启动

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

访问 `http://localhost:3000`。生产构建：

```bash
npm run lint
npm run build
```

Supabase client 在函数内懒初始化，因此 `npm run build` 不要求存在环境变量；页面运行时读取真实数据才需要配置。

## 环境变量

| 变量 | 作用 | 是否暴露到浏览器 |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Project URL | 是 |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key；保留给未来受 RLS 保护的浏览器读取 | 是 |
| `SUPABASE_SERVICE_ROLE_KEY` | 服务端查询及 Feedback 写入 | 否 |
| `OFFSITE_DEALS_TABLE` | Deal 表名，默认 `slickdeals_deals`，迁移后可设 `offsite_deals` | 否 |
| `MONITORED_BRANDS` | 逗号分隔的监控品牌，用于 Dashboard 和 Deals 筛选 | 否 |
| `FEEDBACK_CREATED_BY` | Feedback 创建来源标识，默认 `web-console` | 否 |

`SUPABASE_SERVICE_ROLE_KEY` 只能放在 `.env.local` 或 Vercel Environment Variables 中，不能使用 `NEXT_PUBLIC_` 前缀，也不能提交到 Git。

## Supabase 表依赖

- `agent_runs`：执行 `../sql/007_create_agent_runs.sql`。
- `slickdeals_deals` 或 `offsite_deals`：现有生产 Deal 表。
- `deal_feedback`：执行 `../sql/008_create_deal_feedback.sql`。

Feedback migration 启用 RLS，撤销 anon/authenticated 权限，并只给 service role 读写权限。网页的 Feedback 写入统一经过 `src/app/actions/feedback.ts`。

在 Supabase SQL Editor 执行 migration 后，可用以下 SQL 验证：

```sql
select column_name, data_type
from information_schema.columns
where table_schema = 'public' and table_name = 'deal_feedback'
order by ordinal_position;

select relname, relrowsecurity
from pg_class
where relname = 'deal_feedback';
```

## Vercel 部署

从 GitHub 导入 `TOM0122/overseas-monitor`，项目设置如下：

```text
Root Directory: web
Framework Preset: Next.js
Build Command: npm run build
Install Command: npm install
Output Directory: 留空，使用 Next.js 默认值
```

在 Vercel Project Settings 的 Environment Variables 中配置 `.env.example` 里的变量。至少为 Production 配置；建议 Preview 同步配置一套只读或测试 Supabase 环境。

部署前先执行 `sql/008_create_deal_feedback.sql`。若 SQL 尚未执行，页面仍可显示 Deals，但 Feedback 显示为空且提交会失败。

## Deployment Protection

在 Vercel 项目的 `Settings > Deployment Protection` 中启用 Vercel Authentication，并选择保护范围。第一版依赖这层访问保护，不在应用内实现登录系统。

Vercel 计划限制需要特别注意：Hobby 的 Standard Protection 可保护 Preview 和 Deployment URL，但不保护 Production Domain。若生产域名也必须保持私有，应使用 Pro/Enterprise 的 All Deployments；Hobby 测试期应只共享受保护的 Preview/Deployment URL，不要把未保护的生产域名作为内部入口。

Protection 只控制网页访问，不替代数据库权限。Feedback 表仍依赖 RLS + server-only service role，浏览器端没有写库密钥。

## 常见问题

### 页面显示环境变量缺失

检查 `NEXT_PUBLIC_SUPABASE_URL` 和 `SUPABASE_SERVICE_ROLE_KEY`。修改 Vercel 环境变量后需要重新部署。

### Deal 页面为空

确认 `OFFSITE_DEALS_TABLE` 与生产表名一致。未执行表重命名 migration 时使用 `slickdeals_deals`。

### Feedback 提交失败

确认已执行 `sql/008_create_deal_feedback.sql`，并且 Vercel 中存在正确的 `SUPABASE_SERVICE_ROLE_KEY`。

### Build 成功但页面运行时报权限错误

Build 不访问 Supabase。运行时错误通常来自错误的 key、表名或 Supabase 权限配置。

## 后续扩展

后续可增加在线配置管理、Feedback 反哺排序与排除规则、每周复盘、竞品活跃度评分、价格带分析、Frontpage 分析、新竞品发现和内容机会建议。第一版只沉淀 Feedback，不自动修改 Agent 配置或规则。
