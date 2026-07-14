export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export type RunStatus = "running" | "success" | "partial_success" | "failed" | string;

export interface StepResult {
  name: string;
  status: string;
  count?: number | null;
  duration_seconds?: number | null;
  partial?: boolean;
  partial_reason?: string | null;
  error?: string | null;
}

export interface SourceCounts {
  slickdeals_scraper?: number;
  hip2save_scraper?: number;
  slickdeals?: number;
  hip2save?: number;
  total?: number;
  [key: string]: number | undefined;
}

export interface LlmInfo {
  model?: string;
  latency?: number;
  latency_seconds?: number;
  usage?: JsonValue;
  prompt_tokens?: number;
  completion_tokens?: number;
  reasoning_tokens?: number;
  total_tokens?: number;
  validation_status?: string;
  validator_status?: string;
  retry_count?: number;
  finish_reason?: string;
  fallback?: boolean;
  [key: string]: JsonValue | undefined;
}

export interface PushResult {
  ok?: boolean;
  errcode?: number;
  errmsg?: string;
  original_bytes?: number;
  final_bytes?: number;
  truncated?: boolean;
  [key: string]: JsonValue | undefined;
}

export interface AgentRun {
  id: string;
  started_at: string;
  ended_at: string | null;
  status: RunStatus;
  trigger_type: string | null;
  timezone: string | null;
  report_date: string | null;
  step_results: StepResult[];
  source_counts: SourceCounts;
  quality_alerts: JsonValue[];
  llm_info: LlmInfo;
  report_markdown: string | null;
  push_result: PushResult;
  error_summary: string | null;
  created_at: string;
}

export interface Deal {
  id: number | string;
  deal_id: string;
  source: string | null;
  title: string | null;
  brand: string | null;
  category: string | null;
  price: number | null;
  original_price: number | null;
  discount_pct: number | null;
  url: string | null;
  thumbs_up: number | null;
  comments_count: number | null;
  is_frontpage: boolean | null;
  posted_at: string | null;
  scraped_at: string;
}

export const FEEDBACK_TYPES = [
  "valid",
  "false_positive",
  "important",
  "ignore",
  "brand_candidate",
  "price_watch",
  "content_opportunity",
] as const;

export type FeedbackType = (typeof FEEDBACK_TYPES)[number];

export interface DealFeedback {
  id: number;
  deal_id: string;
  feedback_type: FeedbackType;
  reason: string | null;
  note: string | null;
  created_by: string | null;
  created_at: string;
}

export interface FeedbackSummary {
  latest: DealFeedback;
  count: number;
}

export interface DealWithFeedback extends Deal {
  feedback?: FeedbackSummary;
}

export interface DealFilters {
  dateFrom?: string;
  dateTo?: string;
  source?: string;
  brand?: string;
  category?: string;
  priceMin?: number;
  priceMax?: number;
  discountMin?: number;
  discountMax?: number;
  frontpage?: "yes" | "no";
  feedback?: FeedbackType | "unmarked";
  monitoredOnly?: boolean;
  unknownOnly?: boolean;
  importantOnly?: boolean;
  falsePositiveOnly?: boolean;
  sort?: "time" | "price" | "discount" | "thumbs" | "comments";
  order?: "asc" | "desc";
  limit?: number;
  page?: number;
}

export interface DashboardMetrics {
  totalDeals: number;
  slickdeals: number;
  hip2save: number;
  monitoredDeals: number;
  unknownBrands: number;
  frontpageDeals: number;
  importantFeedback: number;
  falsePositiveFeedback: number;
  lowestPriceDeal: DealWithFeedback | null;
}
