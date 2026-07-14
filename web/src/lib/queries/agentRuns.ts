import "server-only";

import { dayBoundsUtc } from "@/lib/format";
import { getSupabaseReadClient } from "@/lib/supabase/server";
import type { AgentRun } from "@/lib/types";

export interface RunFilters {
  dateFrom?: string;
  dateTo?: string;
  status?: string;
  fallback?: "yes" | "no";
  qualityAlerts?: "yes" | "no";
  hasError?: "yes" | "no";
}

export function normalizeRun(row: Record<string, unknown>): AgentRun {
  return {
    id: String(row.id),
    started_at: String(row.started_at),
    ended_at: row.ended_at ? String(row.ended_at) : null,
    status: String(row.status ?? "unknown"),
    trigger_type: row.trigger_type ? String(row.trigger_type) : null,
    timezone: row.timezone ? String(row.timezone) : null,
    report_date: row.report_date ? String(row.report_date) : null,
    step_results: Array.isArray(row.step_results) ? (row.step_results as AgentRun["step_results"]) : [],
    source_counts: row.source_counts && typeof row.source_counts === "object" ? (row.source_counts as AgentRun["source_counts"]) : {},
    quality_alerts: Array.isArray(row.quality_alerts) ? (row.quality_alerts as AgentRun["quality_alerts"]) : [],
    llm_info: row.llm_info && typeof row.llm_info === "object" ? (row.llm_info as AgentRun["llm_info"]) : {},
    report_markdown: row.report_markdown ? String(row.report_markdown) : null,
    push_result: row.push_result && typeof row.push_result === "object" ? (row.push_result as AgentRun["push_result"]) : {},
    error_summary: row.error_summary ? String(row.error_summary) : null,
    created_at: String(row.created_at ?? row.started_at),
  };
}

export async function getLatestAgentRun(): Promise<AgentRun | null> {
  const { data, error } = await getSupabaseReadClient()
    .from("agent_runs")
    .select("*")
    .order("started_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) throw error;
  return data ? normalizeRun(data) : null;
}

export async function getRecentAgentRuns(limit = 20, filters: RunFilters = {}): Promise<AgentRun[]> {
  let query = getSupabaseReadClient()
    .from("agent_runs")
    .select("*")
    .order("started_at", { ascending: false })
    .limit(Math.min(Math.max(limit, 1), 200));

  if (filters.dateFrom) query = query.gte("started_at", dayBoundsUtc(filters.dateFrom).start);
  if (filters.dateTo) query = query.lt("started_at", dayBoundsUtc(filters.dateTo).end);
  if (filters.status) query = query.eq("status", filters.status);
  if (filters.fallback === "yes") query = query.contains("llm_info", { fallback: true });
  if (filters.fallback === "no") query = query.not("llm_info", "cs", JSON.stringify({ fallback: true }));
  if (filters.hasError === "yes") query = query.not("error_summary", "is", null);
  if (filters.hasError === "no") query = query.is("error_summary", null);

  const { data, error } = await query;
  if (error) throw error;
  let rows = (data ?? []).map((row) => normalizeRun(row));
  if (filters.qualityAlerts === "yes") rows = rows.filter((row) => row.quality_alerts.length > 0);
  if (filters.qualityAlerts === "no") rows = rows.filter((row) => row.quality_alerts.length === 0);
  return rows;
}

export async function getAgentRunById(id: string): Promise<AgentRun | null> {
  const { data, error } = await getSupabaseReadClient()
    .from("agent_runs")
    .select("*")
    .eq("id", id)
    .maybeSingle();
  if (error) throw error;
  return data ? normalizeRun(data) : null;
}
