import { AlertTriangle, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

import { DealFilters } from "@/components/deals/DealFilters";
import { DealTable } from "@/components/deals/DealTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { getDealFilterOptions, getDeals, isFeedbackType } from "@/lib/queries/deals";
import type { DealFilters as DealFilterType, DealWithFeedback } from "@/lib/types";

export const dynamic = "force-dynamic";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;
const one = (value: string | string[] | undefined) => Array.isArray(value) ? value[0] : value;
const numberValue = (value: string | undefined) => value === undefined || value === "" ? undefined : Number(value);

export default async function DealsPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const values = Object.fromEntries(Object.entries(params).map(([key, value]) => [key, one(value)])) as Record<string, string | undefined>;
  const feedback = values.feedback === "unmarked" || isFeedbackType(values.feedback) ? values.feedback : undefined;
  const page = Math.max(Number(values.page) || 1, 1);
  const filters: DealFilterType = {
    dateFrom: values.date_from, dateTo: values.date_to, source: values.source, brand: values.brand, category: values.category,
    priceMin: numberValue(values.price_min), priceMax: numberValue(values.price_max),
    discountMin: numberValue(values.discount_min), discountMax: numberValue(values.discount_max),
    frontpage: values.frontpage === "yes" || values.frontpage === "no" ? values.frontpage : undefined,
    feedback, monitoredOnly: values.monitored === "1", unknownOnly: values.unknown === "1",
    importantOnly: values.important === "1", falsePositiveOnly: values.false_positive === "1",
    sort: ["time", "price", "discount", "thumbs", "comments"].includes(values.sort ?? "") ? values.sort as DealFilterType["sort"] : "time",
    order: values.order === "asc" ? "asc" : "desc", limit: 50, page,
  };

  let deals: DealWithFeedback[] = [];
  let options = { brands: [] as string[], categories: [] as string[] };
  let errorMessage = "";
  try { [deals, options] = await Promise.all([getDeals(filters), getDealFilterOptions()]); }
  catch (error) { console.error("Deals load failed", error); errorMessage = error instanceof Error ? error.message : "Deal 数据读取失败"; }

  const pageHref = (target: number) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(values)) if (value && key !== "page") query.set(key, value);
    if (target > 1) query.set("page", String(target));
    const suffix = query.toString();
    return suffix ? `/deals?${suffix}` : "/deals";
  };
  return (
    <>
      <PageHeader title="Deal 数据复核" description={`查看、筛选并标记站外 Deal。第 ${page} 页，当前显示 ${deals.length} 条。`} />
      <div className="mb-5"><DealFilters values={values} brands={options.brands} categories={options.categories} /></div>
      {errorMessage ? <div className="mb-5 flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"><AlertTriangle className="h-4 w-4" />{errorMessage}</div> : null}
      {deals.length ? <DealTable deals={deals} /> : <EmptyState title="没有符合条件的 Deal" description="调整筛选条件，或确认站外 Deal 表名和 Supabase 权限配置正确。" />}
      <nav className="mt-4 flex items-center justify-end gap-2" aria-label="Deal 分页">
        {page > 1 ? <Link href={pageHref(page - 1)} className="inline-flex h-9 items-center gap-1 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium text-zinc-700 hover:bg-zinc-50"><ChevronLeft className="h-4 w-4" />上一页</Link> : null}
        <span className="px-2 font-mono text-sm text-zinc-500">{page}</span>
        {deals.length === 50 ? <Link href={pageHref(page + 1)} className="inline-flex h-9 items-center gap-1 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium text-zinc-700 hover:bg-zinc-50">下一页<ChevronRight className="h-4 w-4" /></Link> : null}
      </nav>
    </>
  );
}
