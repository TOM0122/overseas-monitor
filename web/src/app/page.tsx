import { AlertTriangle, BadgeDollarSign, CircleDollarSign, MessageSquareWarning, ScanSearch, Tags } from "lucide-react";
import Link from "next/link";

import { DealTable } from "@/components/deals/DealTable";
import { DataTable, type DataColumn } from "@/components/ui/DataTable";
import { DetailGrid } from "@/components/ui/DetailGrid";
import { EmptyState } from "@/components/ui/EmptyState";
import { MetricCard } from "@/components/ui/MetricCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { calculateDashboardMetrics, getPriorityDeals, getTodayDeals } from "@/lib/queries/deals";
import { getLatestAgentRun, getRecentAgentRuns } from "@/lib/queries/agentRuns";
import { formatDate, formatDateTime, formatDuration, formatMoney, jsonArrayLength, pushSucceeded, retryCount, sourceCount, usedFallback, validatorStatus } from "@/lib/format";
import type { AgentRun } from "@/lib/types";

export const dynamic = "force-dynamic";

function trendColumns(): DataColumn<AgentRun>[] {
  return [
    { key: "date", header: "日期", render: (run) => <Link className="font-medium text-zinc-900 hover:text-emerald-700" href={`/runs/${run.id}`}>{formatDate(run.report_date ?? run.started_at)}</Link> },
    { key: "status", header: "状态", render: (run) => <StatusBadge status={run.status}>{run.status}</StatusBadge> },
    { key: "slickdeals", header: "Slickdeals", className: "text-right font-mono", render: (run) => sourceCount(run.source_counts, "slickdeals") },
    { key: "hip2save", header: "hip2save", className: "text-right font-mono", render: (run) => sourceCount(run.source_counts, "hip2save") },
    { key: "validator", header: "Validator", render: (run) => <StatusBadge status={validatorStatus(run.llm_info)}>{validatorStatus(run.llm_info)}</StatusBadge> },
    { key: "fallback", header: "Fallback", render: (run) => usedFallback(run.llm_info) ? <StatusBadge status="fallback">是</StatusBadge> : "否" },
    { key: "push", header: "钉钉推送", render: (run) => pushSucceeded(run.push_result) ? <StatusBadge status="success">成功</StatusBadge> : <StatusBadge status="failed">失败</StatusBadge> },
    { key: "alerts", header: "质量告警", className: "text-right font-mono", render: (run) => jsonArrayLength(run.quality_alerts) },
  ];
}

export default async function DashboardPage() {
  let errorMessage = "";
  let latest: AgentRun | null = null;
  let recent: AgentRun[] = [];
  let deals = [] as Awaited<ReturnType<typeof getTodayDeals>>;
  try {
    [latest, recent, deals] = await Promise.all([getLatestAgentRun(), getRecentAgentRuns(7), getTodayDeals()]);
  } catch (error) {
    console.error("Dashboard data load failed", error);
    errorMessage = error instanceof Error ? error.message : "Dashboard 数据读取失败";
  }
  const metrics = calculateDashboardMetrics(deals);
  const priorityDeals = getPriorityDeals(deals);

  return (
    <>
      <PageHeader title="竞品监控 Dashboard" description="查看今日 Agent 运行、站外 Deal 与人工反馈状态" />
      {errorMessage ? <div className="mb-5 flex gap-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><div><strong>数据暂不可用</strong><p className="mt-1 text-amber-800">{errorMessage}。请检查 Web 环境变量与 Supabase 表权限。</p></div></div> : null}

      <section aria-labelledby="today-run">
        <div className="mb-3 flex items-center justify-between"><h2 id="today-run" className="text-base font-semibold text-zinc-900">今日运行状态</h2>{latest ? <Link href={`/runs/${latest.id}`} className="text-sm font-medium text-emerald-700 hover:text-emerald-900">查看详情</Link> : null}</div>
        {latest ? <DetailGrid items={[
          { label: "状态", value: <StatusBadge status={latest.status}>{latest.status}</StatusBadge> },
          { label: "运行时间", value: formatDateTime(latest.started_at) },
          { label: "总耗时", value: formatDuration(latest.started_at, latest.ended_at) },
          { label: "Slickdeals", value: sourceCount(latest.source_counts, "slickdeals") },
          { label: "hip2save", value: sourceCount(latest.source_counts, "hip2save") },
          { label: "Validator", value: validatorStatus(latest.llm_info) },
          { label: "Retry / Fallback", value: `${retryCount(latest.llm_info)} / ${usedFallback(latest.llm_info) ? "是" : "否"}` },
          { label: "钉钉 / 截断 / 告警", value: `${pushSucceeded(latest.push_result) ? "成功" : "失败"} / ${latest.push_result.truncated ? "是" : "否"} / ${jsonArrayLength(latest.quality_alerts)}` },
        ]} /> : <EmptyState title="暂无运行记录" description="执行 sql/007 并完成一次生产运行后，这里会显示最新 agent_run。" />}
      </section>

      <section className="mt-8" aria-labelledby="metrics"><h2 id="metrics" className="mb-3 text-base font-semibold text-zinc-900">今日核心指标</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          <MetricCard label="今日 Deal 总数" value={metrics.totalDeals} icon={<Tags className="h-4 w-4" />} />
          <MetricCard label="Slickdeals" value={metrics.slickdeals} />
          <MetricCard label="hip2save" value={metrics.hip2save} />
          <MetricCard label="监控品牌 Deal" value={metrics.monitoredDeals} icon={<ScanSearch className="h-4 w-4" />} />
          <MetricCard label="未知品牌 Deal" value={metrics.unknownBrands} />
          <MetricCard label="最低价 Deal" value={formatMoney(metrics.lowestPriceDeal?.price)} detail={metrics.lowestPriceDeal?.brand ?? metrics.lowestPriceDeal?.title ?? "暂无价格"} icon={<CircleDollarSign className="h-4 w-4" />} />
          <MetricCard label="Frontpage Deal" value={metrics.frontpageDeals} icon={<BadgeDollarSign className="h-4 w-4" />} />
          <MetricCard label="重要反馈" value={metrics.importantFeedback} />
          <MetricCard label="误报反馈" value={metrics.falsePositiveFeedback} icon={<MessageSquareWarning className="h-4 w-4" />} />
        </div>
      </section>

      <section className="mt-8" aria-labelledby="trends"><div className="mb-3 flex items-center justify-between"><h2 id="trends" className="text-base font-semibold text-zinc-900">最近 7 次运行</h2><Link href="/runs" className="text-sm font-medium text-emerald-700 hover:text-emerald-900">全部运行</Link></div><DataTable columns={trendColumns()} rows={recent} rowKey={(run) => run.id} emptyText="暂无运行趋势" /></section>
      <section className="mt-8" aria-labelledby="top-deals"><div className="mb-3 flex items-center justify-between"><h2 id="top-deals" className="text-base font-semibold text-zinc-900">今日重点 Deals</h2><Link href="/deals" className="text-sm font-medium text-emerald-700 hover:text-emerald-900">进入复核</Link></div><DealTable deals={priorityDeals} showCategory={false} /></section>
    </>
  );
}
