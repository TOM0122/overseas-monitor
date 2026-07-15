import "server-only";

import { FEEDBACK_TYPES, type FeedbackType } from "@/lib/feedback/constants";
import { dayBoundsUtc, todayInShanghai } from "@/lib/format";
import { getDealFeedbackSummary } from "@/lib/queries/feedback";
import { getOffsiteDealsTable, getSupabaseReadClient } from "@/lib/supabase/server";
import type { DashboardMetrics, Deal, DealFilters, DealWithFeedback } from "@/lib/types";

const DEFAULT_MONITORED_BRANDS = [
  "Aecooly",
  "PlayHot",
  "Gaiatop",
  "SWEETFULL",
  "Coolhill",
  "Shark",
  "Diveblues",
];

export function getMonitoredBrands(): string[] {
  return (process.env.MONITORED_BRANDS || DEFAULT_MONITORED_BRANDS.join(","))
    .split(",")
    .map((brand) => brand.trim())
    .filter(Boolean);
}

function normalizeDeal(row: Record<string, unknown>): Deal {
  const numberOrNull = (value: unknown) => value == null || value === "" ? null : Number(value);
  return {
    id: typeof row.id === "number" ? row.id : String(row.id),
    deal_id: String(row.deal_id),
    source: row.source ? String(row.source) : null,
    title: row.title ? String(row.title) : null,
    brand: row.brand ? String(row.brand) : null,
    category: row.category ? String(row.category) : null,
    price: numberOrNull(row.price),
    original_price: numberOrNull(row.original_price),
    discount_pct: numberOrNull(row.discount_pct),
    url: row.url ? String(row.url) : null,
    thumbs_up: numberOrNull(row.thumbs_up),
    comments_count: numberOrNull(row.comments_count),
    is_frontpage: row.is_frontpage == null ? null : Boolean(row.is_frontpage),
    posted_at: row.posted_at ? String(row.posted_at) : null,
    scraped_at: String(row.scraped_at),
  };
}

function matchesFeedbackFilter(deal: DealWithFeedback, filters: DealFilters): boolean {
  const type = deal.feedback?.latest.feedback_type;
  if (filters.feedback === "unmarked" && type) return false;
  if (filters.feedback && filters.feedback !== "unmarked" && type !== filters.feedback) return false;
  if (filters.importantOnly && type !== "important") return false;
  if (filters.falsePositiveOnly && type !== "false_positive") return false;
  return true;
}

export async function getDeals(filters: DealFilters = {}): Promise<DealWithFeedback[]> {
  const monitored = new Set(getMonitoredBrands().map((brand) => brand.toLowerCase()));
  const sortFields = {
    time: "scraped_at",
    price: "price",
    discount: "discount_pct",
    thumbs: "thumbs_up",
    comments: "comments_count",
  } as const;
  const sortField = sortFields[filters.sort ?? "time"];
  const page = Math.max(filters.page ?? 1, 1);
  const pageSize = Math.min(Math.max(filters.limit ?? 200, 1), 500);
  let query = getSupabaseReadClient()
    .from(getOffsiteDealsTable())
    .select("*")
    .order(sortField, { ascending: filters.order === "asc", nullsFirst: false })
    .limit(Math.min(page * pageSize, 500));

  if (filters.dateFrom) query = query.gte("scraped_at", dayBoundsUtc(filters.dateFrom).start);
  if (filters.dateTo) query = query.lt("scraped_at", dayBoundsUtc(filters.dateTo).end);
  if (filters.source) query = query.eq("source", filters.source);
  if (filters.brand) query = query.eq("brand", filters.brand);
  if (filters.category) query = query.eq("category", filters.category);
  if (filters.priceMin != null) query = query.gte("price", filters.priceMin);
  if (filters.priceMax != null) query = query.lte("price", filters.priceMax);
  if (filters.discountMin != null) query = query.gte("discount_pct", filters.discountMin);
  if (filters.discountMax != null) query = query.lte("discount_pct", filters.discountMax);
  if (filters.frontpage === "yes") query = query.eq("is_frontpage", true);
  if (filters.frontpage === "no") query = query.or("is_frontpage.eq.false,is_frontpage.is.null");
  if (filters.unknownOnly) query = query.is("brand", null);

  const { data, error } = await query;
  if (error) throw error;
  let deals = (data ?? []).map((row) => normalizeDeal(row));
  if (filters.monitoredOnly) deals = deals.filter((deal) => deal.brand && monitored.has(deal.brand.toLowerCase()));

  const summaries = await getDealFeedbackSummary(deals.map((deal) => deal.deal_id));
  const filtered = deals
    .map((deal) => ({ ...deal, feedback: summaries.get(deal.deal_id) }))
    .filter((deal) => matchesFeedbackFilter(deal, filters));
  const offset = (page - 1) * pageSize;
  return filtered.slice(offset, offset + pageSize);
}

export async function getTodayDeals(): Promise<DealWithFeedback[]> {
  const today = todayInShanghai();
  return getDeals({ dateFrom: today, dateTo: today, limit: 500 });
}

export async function getDealFilterOptions(): Promise<{ brands: string[]; categories: string[] }> {
  const { data, error } = await getSupabaseReadClient()
    .from(getOffsiteDealsTable())
    .select("brand,category")
    .order("scraped_at", { ascending: false })
    .limit(1000);
  if (error) throw error;
  const brands = [...new Set((data ?? []).map((row) => row.brand).filter((value): value is string => typeof value === "string" && Boolean(value)))].sort();
  const categories = [...new Set((data ?? []).map((row) => row.category).filter((value): value is string => typeof value === "string" && Boolean(value)))].sort();
  return { brands, categories };
}

export function calculateDashboardMetrics(deals: DealWithFeedback[]): DashboardMetrics {
  const monitored = new Set(getMonitoredBrands().map((brand) => brand.toLowerCase()));
  const priced = deals.filter((deal) => deal.price != null);
  const lowestPriceDeal = priced.sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity))[0] ?? null;
  return {
    totalDeals: deals.length,
    slickdeals: deals.filter((deal) => deal.source?.toLowerCase() === "slickdeals").length,
    hip2save: deals.filter((deal) => deal.source?.toLowerCase() === "hip2save").length,
    monitoredDeals: deals.filter((deal) => deal.brand && monitored.has(deal.brand.toLowerCase())).length,
    unknownBrands: deals.filter((deal) => !deal.brand).length,
    frontpageDeals: deals.filter((deal) => deal.is_frontpage).length,
    importantFeedback: deals.filter((deal) => deal.feedback?.latest.feedback_type === "important").length,
    falsePositiveFeedback: deals.filter((deal) => deal.feedback?.latest.feedback_type === "false_positive").length,
    lowestPriceDeal,
  };
}

export function getPriorityDeals(deals: DealWithFeedback[], limit = 10): DealWithFeedback[] {
  return [...deals]
    .sort((a, b) => {
      const important = Number(b.feedback?.latest.feedback_type === "important") - Number(a.feedback?.latest.feedback_type === "important");
      if (important) return important;
      const frontpage = Number(Boolean(b.is_frontpage)) - Number(Boolean(a.is_frontpage));
      if (frontpage) return frontpage;
      const thumbs = (b.thumbs_up ?? 0) - (a.thumbs_up ?? 0);
      if (thumbs) return thumbs;
      const comments = (b.comments_count ?? 0) - (a.comments_count ?? 0);
      if (comments) return comments;
      return (a.price ?? Infinity) - (b.price ?? Infinity);
    })
    .slice(0, limit);
}

export function isFeedbackType(value: string | undefined): value is FeedbackType {
  return FEEDBACK_TYPES.includes((value ?? "") as FeedbackType);
}
