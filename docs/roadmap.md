# 海外竞品监控 Agent 后续优化路线图

> 定稿于 2026-06-05。本文件是已确认的优先级与分阶段计划；逐 Phase 落地，每个 Phase = 一份实施规格 → 验证 → 上线，再进下一个。

## 优先级

严格按 P0 先行：先做数据质量告警，再做「亚马逊类目前 30 名价格监控」。优先保护现有日报可靠性，再扩展日报信息量。

| 优先级 | 方向 | 结论 |
|---|---|---|
| P0 | 数据质量告警 | 最高优先级。防止站点改版、403、Keepa 异常导致静默少数据。 |
| P1 | 亚马逊类目前 30 名价格监控 | 近期需求，放在告警之后；上线即收缩 BSR，避免报告冗余。 |
| P2 | 趋势分析 | 复用历史快照，适合在 Top30 后做周环比和异动摘要。 |
| P3 | 潜在竞品候选榜 | 有价值，但必须先清理品牌推断噪音；先做人工候选，不自动入白名单。 |
| P4 | Slickdeals Playwright 兜底 | 只做搜索页静态失败兜底，默认关闭或限流；不访问 Deal 详情页。 |
| P5 | 覆盖扩展 | 最后做。hand_warmer、更多 ASIN/品牌、第三渠道都会放大 token、噪音和报告长度压力。 |

## 分阶段计划

### Phase 1：数据质量告警
- 滚动 7/14 天基线：按 source/category 统计 Deal 数、品牌数、有效价格数；按 Keepa 步骤统计 snapshots 与 bestsellers 行数。
- 扩展 `main.py` 现有 `send_pipeline_alert`，复用失败/空步骤的钉钉通道，不新建通道。
- 只做 deterministic 规则，不交给 LLM（如：今日低于历史均值 40% 且低于最小绝对阈值时告警）。
- warn-only，不阻断日报；dry-run 不发告警。

### Phase 2：亚马逊 Top30 价格监控
- 日报模块顺序：① 总览 → ② Top30 价格监控 → ③ BSR 监测 → ④ 站外每日发现 → ⑤ 建议 → ⑥ 注意。
- 扩展 `amazon_bestsellers` 价格字段（`price`/`buy_box_price`/`price_source`）；一次性交付 SQL migration + README + 本地验证命令。
- `amazon_bestseller_scraper` 仅对 Top30 做价格富化（不扩到 Top100），保留 wall-clock timeout 与 token 保护。
- analyzer 增 `amazon_top30_price_monitor` payload（rank/ASIN/brand/price/较昨日变化/是否监控 ASIN）。
- Top30 表硬上限 ≤30 行、不放标题，列只保留「排名 | 品牌 | ASIN | 价格 | 较昨日」。
- 上线首日 `较昨日` 因历史无价格显示「数据缺失」（不用 0），次日起正常。
- **上线即收缩 BSR：日报只渲染 `bsr_monitor.focus`（自有 Diveblues 排名），移除竞品 BSR 表**（payload 可保留 competitors）。竞品排名由 Top30 表承担。
- 验收必须 `--no-push` 实测整份报告 UTF-8 字节数 < 19000。

### Phase 3：趋势分析
- 7 天窗口、同一 `bsr_category_id` 比较价格/BSR。
- 只输出 Top3 异动摘要（自有周环比、竞品最大降价、竞品最大 BSR 异动、新进榜），不扩大正文表格。

### Phase 4：潜在竞品候选榜
- 先修 `infer_brand_from_title`（减少把 Prime/Select/Deal/2-Pack/Portable 等当品牌）。
- 候选来源：已过 fan 类目复核的 unknown/offsite 高频热帖 + amazon_bestsellers untracked Top100。
- 输出人工复核候选 Top5，不自动写入 `brand_list.txt`。

### Phase 5：韧性与覆盖扩展
- Slickdeals 搜索页 Playwright 兜底（feature flag 默认关闭，不访问详情页/不抓浏览量）。
- hand_warmer 先独立日报/独立 category run 验证，不混入 fan 日报。
- 最后才扩 ASIN/品牌或第三站外渠道。

## 硬约束与降级

- 不做 Slickdeals 浏览量（拿不到）；不逐 Deal 访问详情页（403 + 请求量风险）。
- Hip2save 不补造点赞/Frontpage，只用评论数与发布时间。
- Top30 价格只做 Top30，不默认扩到 Top100，避免 Keepa token 失控。
- 报告体量受钉钉 19000 字节硬约束；新增日报模块必须配「字节预算 `--no-push` 实测」；Top30 上线即移除 BSR 竞品表腾预算。
- 新增内容优先 deterministic 摘要，压缩 payload 与表格，规避 DeepSeek 推理 token 与钉钉截断。
- schema 变更一次性交付 migration + README note + 本地验证命令。

## 已知后果（方案 A 取舍）
- BSR 收缩 + 竞品排名交给 Top30 后，**排名掉出前 30 的监控竞品不再出现在报告中**。主力竞品基本在前 30 内，影响很小；如需关注中段竞品，可后续在 Top30 表后补一行「掉出 Top30 的监控竞品」小结。
