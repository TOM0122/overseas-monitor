import { ExternalLink } from "lucide-react";

import { DealFeedbackButtons } from "@/components/deals/DealFeedbackButtons";
import { DataTable, type DataColumn } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { FEEDBACK_LABELS, formatDateTime, formatMoney, formatPercent } from "@/lib/format";
import type { DealWithFeedback } from "@/lib/types";

export function DealTable({ deals, showCategory = true, showActions = true }: { deals: DealWithFeedback[]; showCategory?: boolean; showActions?: boolean }) {
  const columns: DataColumn<DealWithFeedback>[] = [
    { key: "date", header: "日期", className: "w-28 whitespace-nowrap", render: (deal) => formatDateTime(deal.scraped_at) },
    { key: "source", header: "来源", className: "w-24", render: (deal) => deal.source ?? "-" },
    { key: "brand", header: "品牌", className: "w-28", render: (deal) => deal.brand ?? <span className="text-zinc-400">未知</span> },
    { key: "title", header: "标题", className: "min-w-72 max-w-md", render: (deal) => <span className="line-clamp-2 font-medium text-zinc-900">{deal.title ?? "-"}</span> },
    ...(showCategory ? [{ key: "category", header: "类目", className: "w-24", render: (deal: DealWithFeedback) => deal.category ?? "-" }] : []),
    { key: "price", header: "价格", className: "w-24 whitespace-nowrap font-mono", render: (deal) => formatMoney(deal.price) },
    { key: "original", header: "原价", className: "w-24 whitespace-nowrap font-mono text-zinc-500", render: (deal) => formatMoney(deal.original_price) },
    { key: "discount", header: "折扣", className: "w-20 whitespace-nowrap font-mono", render: (deal) => formatPercent(deal.discount_pct) },
    { key: "frontpage", header: "Frontpage", className: "w-24", render: (deal) => deal.is_frontpage ? <StatusBadge status="important">是</StatusBadge> : <span className="text-zinc-400">否</span> },
    { key: "thumbs", header: "点赞", className: "w-16 text-right font-mono", render: (deal) => deal.thumbs_up ?? "-" },
    { key: "comments", header: "评论", className: "w-16 text-right font-mono", render: (deal) => deal.comments_count ?? "-" },
    { key: "feedback", header: "反馈", className: "w-36", render: (deal) => deal.feedback ? <div><StatusBadge status={deal.feedback.latest.feedback_type}>{FEEDBACK_LABELS[deal.feedback.latest.feedback_type]}</StatusBadge><div className="mt-1 text-[11px] text-zinc-400">{deal.feedback.count} 次</div></div> : <span className="text-zinc-400">未标记</span> },
    { key: "link", header: "原链接", className: "w-20", render: (deal) => deal.url ? <a href={deal.url} target="_blank" rel="noreferrer" title="打开原链接" className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-zinc-300 text-zinc-600 hover:bg-zinc-50"><ExternalLink className="h-3.5 w-3.5" /><span className="sr-only">打开原链接</span></a> : "-" },
    ...(showActions ? [{ key: "actions", header: "操作", className: "w-36", render: (deal: DealWithFeedback) => <DealFeedbackButtons dealId={deal.deal_id} title={deal.title ?? deal.deal_id} url={deal.url} /> }] : []),
  ];
  return <DataTable columns={columns} rows={deals} rowKey={(deal) => deal.deal_id} emptyText="当前筛选条件下暂无 Deal" />;
}
