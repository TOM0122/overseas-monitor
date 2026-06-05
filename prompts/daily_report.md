# 竞品监控日报 Prompt

请基于输入 JSON 生成中文 Markdown 日报。只使用输入数据，不要编造，不要把数据中不存在的数字写进报告。

写作风格：精炼、要点优先、短句；去掉套话与重复表述。保持下述六段结构，不要增删段落。

硬性结构要求：输出必须严格包含以下六段，标题文字保持一致：

```markdown
# 竞品监控日报 · {北京时间日期}

## 一、总览

## 二、亚马逊 Top30 价格监控

## 三、BSR 监测

## 四、站外每日发现

## 五、建议

## 六、注意
```

全局口径：
- 品类名称统一用输入中的 `category_label`；自有/重点品牌用 `focus_brand`，二者均来自输入，不要写死。
- 「数据缺失」专指应有但当前缺失的对比数据（如 BSR 今天或昨天、Top30 昨日价格缺失）；某板块本就没有内容时写「暂无数据」或跳过。两者都不要用 0 代替，也不要编造。

各段要求：
- 总览：2-3 句，概括今天 `category_label` 亚马逊 Top30 与站外整体态势，点出最值得注意的 1 个异动；可参考 `trends`，但只写最重要的 1 条。
- 亚马逊 Top30 价格监控：用 `amazon_top30_price_monitor`，只输出紧凑 Markdown 表格，最多 30 行，列「排名 | 品牌 | ASIN | 价格 | 较昨日」。**不要放标题列**。`price` 空写「数据缺失」；`price_change_display` 为「数据缺失」时照写「数据缺失」，尤其 Top30 价格上线首日昨日价格缺失时不要写 0 或持平。
- BSR 监测（辅助板块，极简）：口径为 `bsr_category.name`，只渲染 `bsr_monitor.focus`（自有/重点品牌），用紧凑 Markdown 表格，列「品牌 | ASIN | 当前排名 | 较昨日 | 备注」（必须用 `|` 分隔成多列，不要用斜杠并成一列）；每个 ASIN 只写“#N”和“{rank_change_display}”，不要追加“排名上升/排名下降”解释或百分比。`bsr_monitor.focus` 为空写「暂无自有品牌榜单/快照数据」，不要写“未配置 ASIN”。**不要渲染 `bsr_monitor.competitors` 竞品 BSR 表；Top30 表已经覆盖竞品排名。不要输出“快速异动 / 新进榜 / 上升 / 下降”等任何 `bestseller_monitor` 内容。** 今天或昨天缺数据写「数据缺失」。
- 站外每日发现（重点板块）：先 1-2 句总览——分别说 Slickdeals（`offsite.summary_by_source.slickdeals`：品牌数 `brand_count`、Deal 数 `deal_count`、价位段 `price_min`-`price_max`）与 Hip2save（`offsite.summary_by_source.hip2save` 同上），并点出全站最低价（`offsite.price_range.lowest_price_deal` 的 `brand` 与 `price`）。随后给**两张紧凑 Markdown 表格**，均只列**主要竞品**（监控品牌）的 Deal、按品牌归类；**表格内不放标题**（标题太长影响观感，需要看详情走链接）：
  - **Slickdeals**（数据源 `offsite.slickdeals_competitor_deals`），列「品牌 | 折扣 | Frontpage | 👍 | 💬 | 链接」：`discount_pct` 写「N%」、空写「—」；`is_frontpage` true→「是」/ false→「否」/ 空→「未知」；`thumbs_up`、`comments_count` 写数字、空写「—」；`url` 用 Markdown 链接（文案如「查看」）。**表格正下方加 1-2 句小结**，点出今日 Slickdeals 上最值得注意的竞品 Deal（点赞/评论最高、上了 Frontpage、或折扣最猛的），用「品牌 + 简短标题（取自 `title`）+ 关键数据」描述。
  - **Hip2save**（数据源 `offsite.hip2save_competitor_deals`），列「品牌 | 折扣 | 💬 | 发布日 | 链接」：`posted_at` 只取日期。**表格正下方同样加 1-2 句小结**，从评论热度 / 折扣力度 / 时效角度点出今日 Hip2save 上最值得注意的竞品帖子（同样可用 `title` 描述）。
  - 某来源无主要竞品 Deal，写「今日 Slickdeals/Hip2save 暂无主要竞品 Deal」，不要编造行。逐行表里不放价格与标题（价格在总览，标题在小结/链接里）。非监控品牌只体现在总览计数，不进表。
- 站外价格只能用 `offsite.price_range`，不要从标题年份、mAh、评论数等推断。`offsite` 已过滤为 `category_label` 品类，不要写入其它品类。
- 建议：基于上面**Top30 价格 + 逐 Deal 的折扣 + 热度**给 1-3 条可执行建议。重点关注：Top30 低价竞品、上了 Frontpage、点赞/评论高的竞品 Deal，以及折扣力度异常的。每条须绑定具体数据并给出明确动作（跟价 / 补 Deal / 冲 Frontpage / 调整价位）。禁止空泛建议。
- 注意：列出数据缺失、抓取异常、需人工复核的点；如 `competitor_candidates` 非空，可用一句话列出需人工复核的新兴竞品候选品牌，不要自动说已纳入监控。

输入数据：

```json
{{DATA_JSON}}
```

## 输出格式（钉钉 markdown）
- 分段标题用 `##` / `###`，不要用一级 `#`（钉钉里过大）。
- 列表统一用 `- `，重点用 `**加粗**`；Top30、BSR 监测与站外每日发现可使用紧凑 Markdown 表格，其它段落不要使用表格。
- 段落/小节之间空一行；不要堆叠多余空行，不要用代码块包裹整篇内容。
- 全文务必简洁，正文控制在约 1500 字以内，避免超出钉钉消息长度上限被截断。
