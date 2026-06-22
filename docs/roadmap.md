# 海外竞品监控 Agent 后续优化路线图

> 更新于 2026-06-22。当前产品方向已调整为 **站外-only**：Slickdeals / hip2save 折扣监控 + 四段日报。Keepa、Amazon Best Sellers、Top30、BSR 监测已停用。

## 当前原则

- 日报只回答站外推广问题：竞品在哪些折扣站出现、价格/折扣/热度如何、当天该做什么动作。
- 不再维护站内监控链路，避免 Keepa token、Amazon 口径、榜单准确性和报告篇幅继续消耗阶段二测试精力。
- 任何新增数据源都必须先通过逐字段样本校验，再进入日报。
- 趋势与候选品牌优先用 deterministic 规则，LLM 只负责压缩表达和建议措辞。

## 优先级

| 优先级 | 方向 | 结论 |
|---|---|---|
| P0 | 数据质量告警 | 持续维护。防止 Slickdeals / hip2save 改版、403、0 数据静默进入日报。 |
| P1 | 站外日报质量 | 优先优化四段结构、表格可读性、建议可执行性、钉钉长度控制。 |
| P2 | 站外周趋势 | 基于 `slickdeals_deals` 的 7 天窗口，跟踪重点品牌铺 Deal 频率、最低价、最大折扣。 |
| P3 | 潜在竞品候选 | 从已过滤的站外高频/高热 unknown 品牌中输出人工复核候选，不自动写白名单。 |
| P4 | 抓取韧性 | Slickdeals 静态失败时再考虑 Playwright 兜底，默认关闭并限流。 |
| P5 | 覆盖扩展 | hand_warmer、更多站外渠道或更多品牌放在最后，避免先放大噪音。 |

## 分阶段计划

### Phase 1：数据质量告警

- 滚动 7/14 天基线：按 source/category 统计 Deal 数、品牌数、有效价格数。
- 复用 `main.py` 的钉钉告警通道，不新建通道。
- 只做 deterministic 规则，例如今日低于历史均值 40% 且低于最小绝对阈值时告警。
- warn-only，不阻断日报；dry-run 不发告警。

### Phase 2：站外日报质量

- 四段结构保持稳定：① 总览 → ② 站外每日发现 → ③ 建议 → ④ 注意。
- 站外每日发现优先用紧凑表格，按来源拆 Slickdeals / hip2save。
- 建议必须绑定当天具体数据：品牌、价位、折扣、Frontpage、点赞/评论、7 天趋势。
- 每次 prompt 改动必须用 `--no-push` 实测钉钉渲染和消息字节数。

### Phase 3：站外周趋势

- 7 天窗口聚合重点品牌：Deal 数、最低价、最大折扣。
- 自有品牌单列，其余重点品牌按 Deal 数排序。
- 只在总览和建议中引用最重要的 1-2 个趋势，不扩大正文表格。

### Phase 4：潜在竞品候选

- 候选来源：已过 fan 类目复核的 unknown/offsite 高频热帖。
- 候选指标：出现天数、来源数、站外 Deal 数、热度分。
- 输出人工复核候选 Top5，不自动写入 `brand_list.txt`。

### Phase 5：韧性与覆盖扩展

- Slickdeals 搜索页 Playwright 兜底：feature flag 默认关闭，不访问详情页，不抓浏览量。
- hand_warmer 先独立 category run 验证，不混入 fan 日报。
- 新增站外渠道前，先保存 HTML 样本并做字段级准确性报告。

## 硬约束

- 不做 Slickdeals 浏览量；不逐 Deal 访问详情页。
- hip2save 不补造点赞/Frontpage，只用评论数与发布时间。
- 报告体量受钉钉 19000 字节硬约束；新增内容必须配 `--no-push` 实测。
- schema 变更一次性交付 migration + README note + 本地验证命令。
