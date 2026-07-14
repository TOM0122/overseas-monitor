import { AlertTriangle, Eye } from "lucide-react";
import Link from "next/link";

import { DataTable, type DataColumn } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDate, formatDateTime, jsonArrayLength, pushSucceeded, reportBytes, retryCount, usedFallback, validatorStatus } from "@/lib/format";
import { getReports } from "@/lib/queries/reports";
import type { AgentRun } from "@/lib/types";

export const dynamic = "force-dynamic";

const columns: DataColumn<AgentRun>[] = [
  { key: "date", header: "报告日期", className: "whitespace-nowrap", render: (run) => <Link className="font-medium text-zinc-900 hover:text-emerald-700" href={`/reports/${run.id}`}>{formatDate(run.report_date)}</Link> },
  { key: "time", header: "运行时间", className: "whitespace-nowrap", render: (run) => formatDateTime(run.started_at) },
  { key: "status", header: "状态", render: (run) => <StatusBadge status={run.status}>{run.status}</StatusBadge> },
  { key: "validator", header: "Validator", render: (run) => validatorStatus(run.llm_info) },
  { key: "retry", header: "Retry", className: "text-right font-mono", render: (run) => retryCount(run.llm_info) },
  { key: "fallback", header: "Fallback", render: (run) => usedFallback(run.llm_info) ? <StatusBadge status="fallback">是</StatusBadge> : "否" },
  { key: "bytes", header: "字节数", className: "text-right font-mono", render: (run) => reportBytes(run).toLocaleString() },
  { key: "push", header: "钉钉推送", render: (run) => pushSucceeded(run.push_result) ? <StatusBadge status="success">成功</StatusBadge> : <StatusBadge status="failed">失败</StatusBadge> },
  { key: "alerts", header: "质量告警", className: "text-right font-mono", render: (run) => jsonArrayLength(run.quality_alerts) },
  { key: "action", header: "操作", render: (run) => <Link href={`/reports/${run.id}`} title="查看报告" className="inline-flex h-8 items-center gap-1.5 rounded-md border border-zinc-300 bg-white px-2.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50"><Eye className="h-3.5 w-3.5" />查看</Link> },
];

export default async function ReportsPage() {
  let reports: AgentRun[] = [];
  let errorMessage = "";
  try { reports = await getReports(100); }
  catch (error) { console.error("Reports load failed", error); errorMessage = error instanceof Error ? error.message : "报告历史读取失败"; }
  return (
    <>
      <PageHeader title="报告历史" description="查看已存档的竞品监控报告与生成状态" />
      {errorMessage ? <div className="mb-5 flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"><AlertTriangle className="h-4 w-4" />{errorMessage}</div> : null}
      {reports.length ? <DataTable columns={columns} rows={reports} rowKey={(run) => run.id} /> : <EmptyState title="暂无历史报告" description="报告会从 agent_runs.report_markdown 读取，无需新增报告表。" />}
    </>
  );
}
