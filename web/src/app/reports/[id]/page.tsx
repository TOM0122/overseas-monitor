import { AlertTriangle, ArrowLeft } from "lucide-react";
import Link from "next/link";

import { DetailGrid } from "@/components/ui/DetailGrid";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { MarkdownReportViewer } from "@/components/reports/MarkdownReportViewer";
import { formatDate, formatDateTime, jsonArrayLength, pushSucceeded, reportBytes, retryCount, usageMetric, usedFallback, validatorStatus } from "@/lib/format";
import { getReportByRunId } from "@/lib/queries/reports";
import type { AgentRun } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ReportDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let report: AgentRun | null = null;
  let errorMessage = "";
  try { report = await getReportByRunId(id); }
  catch (error) { console.error("Report load failed", error); errorMessage = error instanceof Error ? error.message : "报告读取失败"; }
  const back = <Link href="/reports" className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium text-zinc-700 hover:bg-zinc-50"><ArrowLeft className="h-4 w-4" />返回报告历史</Link>;
  if (!report || !report.report_markdown) return <><PageHeader title="报告详情" actions={back} />{errorMessage ? <div className="mb-5 flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><AlertTriangle className="h-4 w-4" />{errorMessage}</div> : null}<EmptyState title="未找到该报告" /></>;

  return (
    <>
      <PageHeader title={`竞品监控报告 ${formatDate(report.report_date)}`} description={`生成时间：${formatDateTime(report.started_at)}`} actions={back} />
      <DetailGrid items={[
        { label: "运行状态", value: <StatusBadge status={report.status}>{report.status}</StatusBadge> },
        { label: "LLM model", value: report.llm_info.model ?? "-" }, { label: "Validator", value: validatorStatus(report.llm_info) },
        { label: "Prompt tokens", value: usageMetric(report.llm_info, "prompt_tokens") ?? "-" },
        { label: "Completion tokens", value: usageMetric(report.llm_info, "completion_tokens") ?? "-" },
        { label: "Total tokens", value: usageMetric(report.llm_info, "total_tokens") ?? "-" },
        { label: "Retry", value: retryCount(report.llm_info) }, { label: "Fallback", value: usedFallback(report.llm_info) ? "是" : "否" },
        { label: "钉钉推送", value: pushSucceeded(report.push_result) ? "成功" : "失败" }, { label: "报告字节数", value: reportBytes(report).toLocaleString() },
        { label: "质量告警", value: jsonArrayLength(report.quality_alerts) },
      ]} />
      <div className="mt-8"><MarkdownReportViewer markdown={report.report_markdown} /></div>
    </>
  );
}
