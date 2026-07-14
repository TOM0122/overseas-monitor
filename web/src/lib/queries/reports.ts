import "server-only";

import { getAgentRunById, normalizeRun } from "@/lib/queries/agentRuns";
import { getSupabaseReadClient } from "@/lib/supabase/server";
import type { AgentRun } from "@/lib/types";

export async function getReports(limit = 100): Promise<AgentRun[]> {
  const { data, error } = await getSupabaseReadClient()
    .from("agent_runs")
    .select("*")
    .not("report_markdown", "is", null)
    .order("started_at", { ascending: false })
    .limit(Math.min(Math.max(limit, 1), 200));
  if (error) throw error;
  return (data ?? []).map((row) => normalizeRun(row));
}

export async function getReportByRunId(id: string): Promise<AgentRun | null> {
  const run = await getAgentRunById(id);
  return run?.report_markdown ? run : null;
}
