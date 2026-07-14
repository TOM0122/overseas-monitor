import { ArrowLeft, AlertTriangle } from "lucide-react";
import Link from "next/link";

import { DataTable, type DataColumn } from "@/components/ui/DataTable";
import { DetailGrid } from "@/components/ui/DetailGrid";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { MarkdownReportViewer } from "@/components/reports/MarkdownReportViewer";
import { formatDate, formatDateTime, formatDuration, formatJsonValue, formatSeconds, jsonArrayLength, pushSucceeded, retryCount, sourceCount, usageMetric, usedFallback, validatorStatus } from "@/lib/format";
import { getAgentRunById } from "@/lib/queries/agentRuns";
import type { AgentRun, StepResult } from "@/lib/types";

export const dynamic = "force-dynamic";

const stepColumns: DataColumn<StepResult>[] = [
  { key: "name", header: "Step", render: (step) => <span className="font-mono text-xs font-medium text-zinc-900">{step.name}</span> },
  { key: "status", header: "状态", render: (step) => <StatusBadge status={step.status}>{step.status}</StatusBadge> },
  { key: "count", header: "数量", className: "text-right font-mono", render: (step) => step.count ?? "-" },
  { key: "duration", header: "耗时", className: "font-mono", render: (step) => formatSeconds(step.duration_seconds) },
  { key: "partial", header: "Partial", render: (step) => step.partial ? <StatusBadge status="fallback">是</StatusBadge> : "否" },
  { key: "reason", header: "Partial reason", className: "max-w-xs", render: (step) => step.partial_reason ?? "-" },
  { key: "error", header: "错误", className: "max-w-xs", render: (step) => step.error ? <span className="text-red-700">{step.error}</span> : "-" },
];

export default async function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let run: AgentRun | null = null;
  let errorMessage = "";
  try { run = await getAgentRunById(id); }
  catch (error) { console.error("Run detail load failed", error); errorMessage = error instanceof Error ? error.message : "运行详情读取失败"; }
  if (!run) return <><PageHeader title="运行详情" actions={<Link href="/runs" className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm"><ArrowLeft className="h-4 w-4" />返回</Link>} />{errorMessage ? <div className="mb-4 flex gap-2 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><AlertTriangle className="h-4 w-4" />{errorMessage}</div> : null}<EmptyState title="未找到该运行记录" /></>;

  const usage = run.llm_info.usage;
  return (
    <>
      <PageHeader title="运行详情" description={`Run ID: ${run.id}`} actions={<Link href="/runs" className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium text-zinc-700 hover:bg-zinc-50"><ArrowLeft className="h-4 w-4" />返回运行记录</Link>} />
      <section><h2 className="mb-3 text-base font-semibold">基本信息</h2><DetailGrid items={[
        { label: "状态", value: <StatusBadge status={run.status}>{run.status}</StatusBadge> }, { label: "Trigger", value: run.trigger_type ?? "-" },
        { label: "开始时间", value: formatDateTime(run.started_at) }, { label: "结束时间", value: formatDateTime(run.ended_at) },
        { label: "总耗时", value: formatDuration(run.started_at, run.ended_at) }, { label: "报告日期", value: formatDate(run.report_date) },
        { label: "时区", value: run.timezone ?? "-" }, { label: "错误摘要", value: run.error_summary ?? "无" },
      ]} /></section>

      <section className="mt-8"><h2 className="mb-3 text-base font-semibold">Step Results</h2><DataTable columns={stepColumns} rows={run.step_results} rowKey={(step) => step.name} emptyText="暂无 Step 记录" /></section>
      <section className="mt-8"><h2 className="mb-3 text-base font-semibold">Source Counts</h2><DetailGrid items={[
        { label: "Slickdeals", value: sourceCount(run.source_counts, "slickdeals") }, { label: "hip2save", value: sourceCount(run.source_counts, "hip2save") },
        { label: "Total", value: run.source_counts.total ?? Object.values(run.source_counts).reduce<number>((sum, value) => sum + (value ?? 0), 0) },
      ]} /></section>
      <section className="mt-8"><h2 className="mb-3 text-base font-semibold">LLM Info</h2><DetailGrid items={[
        { label: "Model", value: run.llm_info.model ?? "-" }, { label: "Latency", value: formatSeconds(Number(run.llm_info.latency_seconds ?? run.llm_info.latency ?? NaN)) },
        { label: "Prompt tokens", value: usageMetric(run.llm_info, "prompt_tokens") ?? "-" }, { label: "Completion tokens", value: usageMetric(run.llm_info, "completion_tokens") ?? "-" },
        { label: "Reasoning tokens", value: usageMetric(run.llm_info, "reasoning_tokens") ?? "-" }, { label: "Total tokens", value: usageMetric(run.llm_info, "total_tokens") ?? "-" },
        { label: "Validator", value: validatorStatus(run.llm_info) }, { label: "Retry / Fallback", value: `${retryCount(run.llm_info)} / ${usedFallback(run.llm_info) ? "是" : "否"}` },
        { label: "Finish reason", value: run.llm_info.finish_reason ?? "-" }, { label: "Usage", value: <pre className="whitespace-pre-wrap font-mono text-xs">{formatJsonValue(usage)}</pre> },
      ]} /></section>
      <section className="mt-8"><h2 className="mb-3 text-base font-semibold">Push Result</h2><DetailGrid items={[
        { label: "推送", value: pushSucceeded(run.push_result) ? <StatusBadge status="success">成功</StatusBadge> : <StatusBadge status="failed">失败</StatusBadge> },
        { label: "errcode", value: run.push_result.errcode ?? "-" }, { label: "errmsg", value: run.push_result.errmsg ?? "-" },
        { label: "原始字节", value: run.push_result.original_bytes ?? "-" }, { label: "最终字节", value: run.push_result.final_bytes ?? "-" },
        { label: "是否截断", value: run.push_result.truncated ? <StatusBadge status="truncated">是</StatusBadge> : "否" },
      ]} /></section>
      <section className="mt-8"><h2 className="mb-3 text-base font-semibold">Quality Alerts <span className="font-mono text-sm text-zinc-400">({jsonArrayLength(run.quality_alerts)})</span></h2>{run.quality_alerts.length ? <div className="rounded-md border border-amber-200 bg-amber-50 p-4"><ul className="space-y-2 text-sm text-amber-900">{run.quality_alerts.map((alert, index) => <li key={index}>{formatJsonValue(alert)}</li>)}</ul></div> : <EmptyState title="暂无质量告警" />}</section>
      {run.report_markdown ? <div className="mt-8"><MarkdownReportViewer markdown={run.report_markdown} /></div> : <div className="mt-8"><EmptyState title="该运行没有报告 Markdown" /></div>}
    </>
  );
}
