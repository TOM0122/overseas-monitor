import "server-only";

import type { FeedbackType } from "@/lib/feedback/constants";
import { getSupabaseAdminClient, getSupabaseReadClient } from "@/lib/supabase/server";
import type { DealFeedback, FeedbackSummary } from "@/lib/types";

function normalizeFeedback(row: Record<string, unknown>): DealFeedback {
  return {
    id: Number(row.id),
    deal_id: String(row.deal_id),
    feedback_type: String(row.feedback_type) as FeedbackType,
    reason: row.reason ? String(row.reason) : null,
    note: row.note ? String(row.note) : null,
    created_by: row.created_by ? String(row.created_by) : null,
    created_at: String(row.created_at),
  };
}

export async function getDealFeedbackSummary(dealIds: string[]): Promise<Map<string, FeedbackSummary>> {
  const ids = [...new Set(dealIds.filter(Boolean))];
  if (!ids.length) return new Map();

  const allRows: DealFeedback[] = [];
  for (let index = 0; index < ids.length; index += 100) {
    const chunk = ids.slice(index, index + 100);
    const { data, error } = await getSupabaseReadClient()
      .from("deal_feedback")
      .select("*")
      .in("deal_id", chunk)
      .order("created_at", { ascending: false });
    if (error) {
      // Migration may not be applied yet. Deals remain readable without feedback.
      if (["42P01", "42501", "PGRST205"].includes(error.code ?? "")) return new Map();
      throw error;
    }
    allRows.push(...(data ?? []).map((row) => normalizeFeedback(row)));
  }

  const summaries = new Map<string, FeedbackSummary>();
  for (const row of allRows) {
    const current = summaries.get(row.deal_id);
    if (!current) summaries.set(row.deal_id, { latest: row, count: 1 });
    else current.count += 1;
  }
  return summaries;
}

export async function createDealFeedback(input: {
  deal_id: string;
  feedback_type: FeedbackType;
  reason?: string | null;
  note?: string | null;
  created_by?: string | null;
}): Promise<DealFeedback> {
  const { data, error } = await getSupabaseAdminClient()
    .from("deal_feedback")
    .insert(input)
    .select("*")
    .single();
  if (error) throw error;
  return normalizeFeedback(data);
}
