import type { ReactNode } from "react";

const STATUS_STYLES: Record<string, string> = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  partial_success: "border-amber-200 bg-amber-50 text-amber-800",
  failed: "border-red-200 bg-red-50 text-red-800",
  running: "border-blue-200 bg-blue-50 text-blue-800",
  ok: "border-emerald-200 bg-emerald-50 text-emerald-800",
  valid: "border-emerald-200 bg-emerald-50 text-emerald-800",
  important: "border-rose-200 bg-rose-50 text-rose-800",
  false_positive: "border-red-200 bg-red-50 text-red-800",
  ignore: "border-zinc-200 bg-zinc-100 text-zinc-700",
  brand_candidate: "border-violet-200 bg-violet-50 text-violet-800",
  price_watch: "border-blue-200 bg-blue-50 text-blue-800",
  content_opportunity: "border-cyan-200 bg-cyan-50 text-cyan-800",
  fallback: "border-amber-200 bg-amber-50 text-amber-800",
  truncated: "border-amber-200 bg-amber-50 text-amber-800",
};

export function StatusBadge({ status, children }: { status: string; children?: ReactNode }) {
  const key = status.toLowerCase();
  return (
    <span className={`inline-flex min-h-6 items-center whitespace-nowrap rounded-[4px] border px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[key] ?? "border-zinc-200 bg-zinc-50 text-zinc-700"}`}>
      {children ?? status}
    </span>
  );
}
