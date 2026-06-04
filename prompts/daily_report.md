# 竞品监控日报 Prompt

请基于输入 JSON 生成中文 Markdown 日报。只使用输入数据，不要编造，不要把数据中不存在的数字写进报告。

写作风格：精炼、要点优先、短句；去掉套话与重复表述。保持下述五段结构，不要增删段落。

硬性结构要求：输出必须严格包含以下五段，标题文字保持一致：

```markdown
# 竞品监控日报 · {北京时间日期}

## 一、总览

## 二、BSR 监测

## 三、站外每日发现

## 四、建议

## 五、注意
```

全局口径：
- 品类名称统一用输入中的 `category_label`；自有/重点品牌用 `focus_brand`，二者均来自输入，不要写死。
- 「数据缺失」专指应有但当前缺失的对比数据（如 BSR 今天或昨天）；某板块本就没有内容时写「暂无数据」或跳过。两者都不要用 0 代替，也不要编造。

各段要求：
- 总览：2-3 句，概括今天 `category_label` 站外整体态势，点出最值得注意的 1 个异动。
- BSR 监测：口径为 `bsr_category.name`，优先使用 `bsr_monitor` 中 `source=amazon_bestsellers` 的类目榜单 rank。先写 `bsr_monitor.focus`（自有品牌已指定 ASIN）的当前排名和较昨日变化，再写 `bsr_monitor.competitors`。自有 ASIN 和竞品 ASIN 均用紧凑 Markdown 表格呈现，建议列为「品牌 / ASIN / 当前排名 / 较昨日 / 备注」；每个 ASIN 只写“#N”和“{rank_change_display}”，不要再追加“排名上升/排名下降”等重复解释，也不要写百分比。如果 `bsr_monitor.focus` 为空，只能写「暂无自有品牌榜单/快照数据」，不要写“未配置 ASIN”。随后只简述 `bestseller_monitor.rank_gainers` / `rank_droppers` 中的快速异动 ASIN，每个异动 ASIN 须带出品牌（`brand`）与简短标题（`title`），并标注是否 `focus_brand` 或重点竞品；不要表述 `bestseller_monitor.new_entries`。`brand` 为空时写「品牌未知」。今天或昨天缺数据写「数据缺失」。
- 站外每日发现（重点）：先用 1-2 句汇总——今天 Slickdeals / hip2save 上共有几家 `category_label` 品牌（`offsite.brand_count`）、整体促销价格区间（`offsite.price_range.min`-`offsite.price_range.max`）、最低价品牌及价格（`offsite.price_range.lowest_price_deal` 的 `brand` 与 `price`）。随后把 `offsite.monitored_brands` 用紧凑 Markdown 表格呈现，列固定为「品牌 / Deal数 / 价位段 / 折扣力度 / 自有」：`focus_brand` 排第一行，「自有」列标 ✓，其余品牌该列留空；其余行按 `deal_count` 从多到少排列。价位段用 `price_min`-`price_max`（如 `$6.79-$16.50`；两者相等只写一个价；为空写「—」）。折扣力度用 `discount_min`-`discount_max`（如 `35%-58%`；相等只写一个；为空写「—」）。价格只能取自上述字段，不要从标题年份 / mAh / 评论数推断。非重点品牌不进表，用一行带过：「其它品牌：BrandA(2)、BrandB(1)」（取自 `offsite.other_brands`，按出现次数）；无则省略该行。`offsite.monitored_brands` 为空时写「今日暂无重点监控品牌的站外 Deal」，不要编造行。
- 价格只能用 `offsite.price_range`，不要从标题年份、mAh、评论数等推断。`offsite` 已过滤为 `category_label` 品类，不要写入其它品类。
- 建议：给 1-3 条可执行的站外运营建议，每条须绑定当天具体数据（某品牌/某价位/Deal 数/折扣），并给出明确动作（如跟价、补 Deal、调整价位段、关注某竞品上新），禁止空泛建议。
- 注意：列出数据缺失、抓取异常、需人工复核的点。
- 不要输出 Amazon 价格表、评分表、评论数表，也不要写「今日新增 ASIN」。

输入数据：

```json
{{DATA_JSON}}
```

## 输出格式（钉钉 markdown）
- 分段标题用 `##` / `###`，不要用一级 `#`（钉钉里过大）。
- 列表统一用 `- `，重点用 `**加粗**`；BSR 监测与站外每日发现可使用紧凑 Markdown 表格，其它段落不要使用表格。
- 段落/小节之间空一行；不要堆叠多余空行，不要用代码块包裹整篇内容。
- 全文务必简洁，正文控制在约 1500 字以内，避免超出钉钉消息长度上限被截断。
