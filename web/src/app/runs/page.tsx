import { AlertTriangle, Search } from "lucide-react";
import Link from "next/link";

import { DataTable, type DataColumn } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDate, formatDateTime, formatDuration, jsonArrayLength, pushSucceeded, retryCount, sourceCount, usedFallback, validatorStatus } from "@/lib/format";
import { getRecentAgentRuns, type RunFilters } from "@/lib/queries/agentRuns";
import type { AgentRun } from "@/lib/types";

export const dynamic = "force-dynamic";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;
const one = (value: string | string[] | undefined) => Array.isArray(value) ? value[0] : value;

function columns(): DataColumn<AgentRun>[] {
  return [
    { key: "time", header: "运行时间", className: "w-36 whitespace-nowrap", render: (run) => <Link href={`/runs/${run.id}`} className="font-medium text-zinc-900 hover:text-emerald-700">{formatDateTime(run.started_at)}</Link> },
    { key: "status", header: "状态", render: (run) => <StatusBadge status={run.status}>{run.status}</StatusBadge> },
    { key: "date", header: "报告日期", className: "whitespace-nowrap", render: (run) => formatDate(run.report_date) },
    { key: "slickdeals", header: "Slickdeals", className: "text-right font-mono", render: (run) => sourceCount(run.source_counts, "slickdeals") },
    { key: "hip2save", header: "hip2save", className: "text-right font-mono", render: (run) => sourceCount(run.source_counts, "hip2save") },
    { key: "duration", header: "总耗时", className: "whitespace-nowrap font-mono", render: (run) => formatDuration(run.started_at, run.ended_at) },
    { key: "validator", header: "Validator", render: (run) => validatorStatus(run.llm_info) },
    { key: "retry", header: "Retry", className: "text-right font-mono", render: (run) => retryCount(run.llm_info) },
    { key: "fallback", header: "Fallback", render: (run) => usedFallback(run.llm_info) ? <StatusBadge status="fallback">是</StatusBadge> : "否" },
    { key: "push", header: "钉钉", render: (run) => pushSucceeded(run.push_result) ? <StatusBadge status="success">成功</StatusBadge> : <StatusBadge status="failed">失败</StatusBadge> },
    { key: "alerts", header: "质量告警", className: "text-right font-mono", render: (run) => jsonArrayLength(run.quality_alerts) },
    { key: "error", header: "错误摘要", className: "max-w-xs", render: (run) => run.error_summary ? <span className="line-clamp-2 text-red-700">{run.error_summary}</span> : <span className="text-zinc-400">无</span> },
  ];
}

export default async function RunsPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const values = Object.fromEntries(Object.entries(params).map(([key, value]) => [key, one(value)])) as Record<string, string | undefined>;
  const filters: RunFilters = {
    dateFrom: values.date_from,
    dateTo: values.date_to,
    status: values.status,
    fallback: values.fallback as RunFilters["fallback"],
    qualityAlerts: values.quality_alerts as RunFilters["qualityAlerts"],
    hasError: values.has_error as RunFilters["hasError"],
  };
  let runs: AgentRun[] = [];
  let errorMessage = "";
  try { runs = await getRecentAgentRuns(100, filters); }
  catch (error) { console.error("Runs load failed", error); errorMessage = error instanceof Error ? error.message : "运行记录读取失败"; }
  const input = "mt-1 h-9 w-full rounded-md border border-zinc-300 bg-white px-2.5 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100";
  return (
    <>
      <PageHeader title="运行记录" description="查看 Agent 每次执行的步骤、耗时、质量告警与推送结果" />
      <form className="mb-5 grid gap-3 rounded-md border border-zinc-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-6">
        <label className="text-xs font-medium text-zinc-600">开始日期<input type="date" name="date_from" defaultValue={values.date_from} className={input} /></label>
        <label className="text-xs font-medium text-zinc-600">结束日期<input type="date" name="date_to" defaultValue={values.date_to} className={input} /></label>
        <label className="text-xs font-medium text-zinc-600">状态<select name="status" defaultValue={values.status ?? ""} className={input}><option value="">全部</option><option value="success">success</option><option value="partial_success">partial_success</option><option value="failed">failed</option><option value="running">running</option></select></label>
        <label className="text-xs font-medium text-zinc-600">Fallback<select name="fallback" defaultValue={values.fallback ?? ""} className={input}><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
        <label className="text-xs font-medium text-zinc-600">质量告警<select name="quality_alerts" defaultValue={values.quality_alerts ?? ""} className={input}><option value="">全部</option><option value="yes">有</option><option value="no">无</option></select></label>
        <label className="text-xs font-medium text-zinc-600">错误<select name="has_error" defaultValue={values.has_error ?? ""} className={input}><option value="">全部</option><option value="yes">有</option><option value="no">无</option></select></label>
        <div className="flex items-end gap-2 sm:col-span-2 lg:col-span-6"><button type="submit" className="inline-flex h-9 items-center gap-2 rounded-md bg-zinc-900 px-4 text-sm font-medium text-white hover:bg-zinc-700"><Search className="h-4 w-4" />筛选</button><Link href="/runs" className="inline-flex h-9 items-center rounded-md border border-zinc-300 px-4 text-sm font-medium text-zinc-700 hover:bg-zinc-50">重置</Link></div>
      </form>
      {errorMessage ? <div className="mb-5 flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"><AlertTriangle className="h-4 w-4" />{errorMessage}</div> : null}
      {runs.length ? <DataTable columns={columns()} rows={runs} rowKey={(run) => run.id} /> : <EmptyState title="暂无运行记录" description="调整筛选条件，或确认 agent_runs migration 已执行。" />}
    </>
  );
}
