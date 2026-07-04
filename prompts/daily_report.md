# 竞品监控日报 Prompt

请基于输入 JSON 生成中文 Markdown 日报。只使用输入数据，不要编造，不要把数据中不存在的数字写进报告。

写作风格：精炼、要点优先、短句；去掉套话与重复表述。保持下述四段结构，不要增删段落。

硬性结构要求：输出必须严格包含以下四段，标题文字保持一致：

```markdown
竞品监控日报 · {北京时间日期}

## 一、总览

## 二、站外每日发现

## 三、建议

## 四、注意
```

全局口径：
- 品类名称统一用输入中的 `category_label`；自有/重点品牌用 `focus_brand`，二者均来自输入，不要写死。
- 本报告只分析站外折扣数据（Slickdeals / hip2save）。不要加入输入 JSON 中不存在的站内监控内容。
- 「数据缺失」专指应有但当前缺失的字段；某板块本就没有内容时写「暂无数据」或跳过。两者都不要用 0 代替，也不要编造。

各段要求：
- 总览：2-3 句，概括今天 `category_label` 站外整体态势，点出最值得注意的 1 个站外异动；可参考 `trends.focus_weekly` / `trends.competitor_weekly`，但只写最重要的 1 条。
- 站外每日发现（重点板块）：先 1-2 句总览——分别说 Slickdeals（`offsite.summary_by_source.slickdeals`：品牌数 `brand_count`、Deal 数 `deal_count`、价位段 `price_min`-`price_max`）与 hip2save（`offsite.summary_by_source.hip2save` 同上），并点出全站最低价（`offsite.price_range.lowest_price_deal` 的 `brand` 与 `price`）。随后给**两张紧凑 Markdown 表格**，均只列**主要竞品**（监控品牌）的 Deal、按品牌归类；**表格内不放标题**（标题太长影响观感，需要看详情走链接）：
  - **Slickdeals**（数据源 `offsite.slickdeals_competitor_deals`），列「品牌 | 折扣 | 折扣价格 | Frontpage | 👍 | 💬 | 链接」：`discount_pct` 写「N%」、空写「—」；`折扣价格` 取 `price` 写「$N」、空写「—」；`is_frontpage` true→「是」/ false→「否」/ 空→「未知」；`thumbs_up`、`comments_count` 写数字、空写「—」；`url` 用 Markdown 链接（文案如「查看」）。**表格正下方加 1-2 句小结**，点出今日 Slickdeals 上最值得注意的竞品 Deal（点赞/评论最高、上了 Frontpage、或折扣最猛的），用「品牌 + 简短标题（取自 `title`）+ 关键数据」描述。
  - **hip2save**（数据源 `offsite.hip2save_competitor_deals`），列「品牌 | 折扣 | 折扣价格 | 💬 | 发布日 | 链接」：`折扣价格` 取 `price` 写「$N」、空写「—」；`posted_at` 只取日期。**表格正下方同样加 1-2 句小结**，从评论热度 / 折扣力度 / 时效角度点出今日 hip2save 上最值得注意的竞品帖子（同样可用 `title` 描述）。
  - 某来源无主要竞品 Deal，写「今日 Slickdeals/hip2save 暂无主要竞品 Deal」，不要编造行。逐行表里不放标题；折扣价格即该 Deal 的 `price`。非监控品牌只体现在总览计数，不进表。
- 站外价格只能用 `offsite.price_range`、`offsite.slickdeals_competitor_deals`、`offsite.hip2save_competitor_deals`、`trends` 中已有字段，不要从标题年份、mAh、评论数等推断。`offsite` 已过滤为 `category_label` 品类，不要写入其它品类。
- 建议：**优先改写 `insights.suggestion_candidates` 里已生成的建议**（这些是代码根据规则算好的，请用简洁中文表达，不要新增与数据无关的判断）；若 `insights.suggestion_candidates` 为空，再基于**逐 Deal 的折扣、价格、Frontpage、点赞/评论热度、7 天站外趋势**补 1-2 条，每条须绑定具体数据并给出明确动作（跟价 / 补 Deal / 冲 Frontpage / 调整价位 / 复核新兴品牌）。禁止空泛或凭空发明的建议。也可参考 `insights.top_heat_deal` / `insights.lowest_price_deal` / `insights.frontpage_deals`。
- 注意：列出数据缺失、抓取异常、需人工复核的点；如 `competitor_candidates` 非空，可用一句话列出需人工复核的新兴竞品候选品牌，不要自动说已纳入监控。

输入数据：

```json
{{DATA_JSON}}
```

## 输出格式（钉钉 markdown）
- 日报标题行不要加 `#`；分段标题用 `##` / `###`，不要用一级 `#`（钉钉里过大）。
- 列表统一用 `- `，重点用 `**加粗**`；站外每日发现可使用紧凑 Markdown 表格，其它段落不要使用表格。
- 段落/小节之间空一行；不要堆叠多余空行，不要用代码块包裹整篇内容。
- 全文务必简洁，正文控制在约 1500 字以内，避免超出钉钉消息长度上限被截断。
