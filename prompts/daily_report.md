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
- BSR 监测：口径为 `bsr_category.name`。先写 `bsr_monitor.focus`（自有品牌已指定 ASIN）的排名，再写 `bsr_monitor.competitors`；随后用 `bestseller_monitor` 简述类目榜单的新进榜、快速上升 ASIN。BSR 数值下降=排名变好，上升=排名变差。今天或昨天缺数据写「数据缺失」。
- 站外每日发现（重点）：先给一段汇总——今天 Slickdeals / hip2save 上共有几家 `category_label` 品牌（`offsite.brand_count`）、促销价格区间（`offsite.price_range`）、最低价品牌及价格（`offsite.price_range.lowest_price_deal`）。随后按品牌展开：优先 `focus_brand`，再写其它重点监控品牌（`offsite.monitored_brands`，含 Deal 数、价位段、折扣力度），非重点品牌归入「其它品牌」。
- 价格只能用 `offsite.price_range`，不要从标题年份、mAh、评论数等推断。`offsite` 已过滤为 `category_label` 品类，不要写入其它品类。
- 建议：给 1-3 条可执行的站外运营建议，每条须绑定当天具体数据（某品牌/某价位/Deal 数/折扣），并给出明确动作（如跟价、补 Deal、调整价位段、关注某竞品上新），禁止空泛建议。
- 注意：列出数据缺失、抓取异常、需人工复核的点。
- 不要输出 Amazon 价格表、评分表、评论数表，也不要写「今日新增 ASIN」。

输入数据：

```json
{{DATA_JSON}}
```
