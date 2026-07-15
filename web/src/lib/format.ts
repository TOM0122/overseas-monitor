import type { AgentRun, JsonValue, LlmInfo, PushResult, SourceCounts } from "@/lib/types";

const DISPLAY_TIMEZONE = "Asia/Shanghai";

export function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: DISPLAY_TIMEZONE,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatDate(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value.length === 10 ? `${value}T00:00:00+08:00` : value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: DISPLAY_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export function formatDuration(startedAt?: string | null, endedAt?: string | null): string {
  if (!startedAt || !endedAt) return "-";
  const seconds = Math.max(0, (new Date(endedAt).getTime() - new Date(startedAt).getTime()) / 1000);
  if (!Number.isFinite(seconds)) return "-";
  if (seconds < 60) return `${seconds.toFixed(1)} 秒`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes} 分 ${rest} 秒`;
}

export function formatSeconds(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return value < 60 ? `${value.toFixed(1)} 秒` : `${Math.floor(value / 60)} 分 ${Math.round(value % 60)} 秒`;
}

export function formatMoney(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

export function formatPercent(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${Number.isInteger(value) ? value : value.toFixed(1)}%`;
}

export function sourceCount(counts: SourceCounts, source: "slickdeals" | "hip2save"): number {
  return counts[`${source}_scraper`] ?? counts[source] ?? 0;
}

export function validatorStatus(info: LlmInfo): string {
  return String(info.validation_status ?? info.validator_status ?? "unknown");
}

export function retryCount(info: LlmInfo): number {
  return typeof info.retry_count === "number" ? info.retry_count : 0;
}

export function usedFallback(info: LlmInfo): boolean {
  return info.fallback === true || info.validation_status === "fallback";
}

export function usageMetric(info: LlmInfo, key: "prompt_tokens" | "completion_tokens" | "reasoning_tokens" | "total_tokens"): number | null {
  const direct = info[key];
  if (typeof direct === "number") return direct;
  const usage = info.usage;
  if (!usage || typeof usage !== "object" || Array.isArray(usage)) return null;
  const value = usage[key];
  if (typeof value === "number") return value;
  if (key === "reasoning_tokens") {
    const details = usage.completion_tokens_details;
    if (details && typeof details === "object" && !Array.isArray(details) && typeof details.reasoning_tokens === "number") return details.reasoning_tokens;
  }
  return null;
}

export function pushSucceeded(result: PushResult): boolean {
  return result.ok === true || result.errcode === 0;
}

export function reportBytes(run: AgentRun): number {
  return run.report_markdown ? new TextEncoder().encode(run.report_markdown).length : 0;
}

export function formatJsonValue(value: JsonValue | undefined): string {
  if (value == null) return "-";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value, null, 2);
}

export function todayInShanghai(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: DISPLAY_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function dayBoundsUtc(date: string): { start: string; end: string } {
  const start = new Date(`${date}T00:00:00+08:00`);
  const end = new Date(start.getTime() + 24 * 60 * 60 * 1000);
  return { start: start.toISOString(), end: end.toISOString() };
}

export function jsonArrayLength(value: JsonValue[] | null | undefined): number {
  return Array.isArray(value) ? value.length : 0;
}
