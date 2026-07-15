import { RotateCcw, Search } from "lucide-react";
import Link from "next/link";

import { FEEDBACK_LABELS, FEEDBACK_TYPES } from "@/lib/feedback/constants";

type Values = Record<string, string | undefined>;

export function DealFilters({ values, brands, categories }: { values: Values; brands: string[]; categories: string[] }) {
  const inputClass = "h-9 min-w-0 rounded-md border border-zinc-300 bg-white px-2.5 text-sm text-zinc-700 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100";
  return (
    <form method="get" className="rounded-md border border-zinc-200 bg-white p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
        <label className="text-xs font-medium text-zinc-600">开始日期<input name="date_from" type="date" defaultValue={values.date_from} className={`mt-1 w-full ${inputClass}`} /></label>
        <label className="text-xs font-medium text-zinc-600">结束日期<input name="date_to" type="date" defaultValue={values.date_to} className={`mt-1 w-full ${inputClass}`} /></label>
        <label className="text-xs font-medium text-zinc-600">来源<select name="source" defaultValue={values.source ?? ""} className={`mt-1 w-full ${inputClass}`}><option value="">全部</option><option value="slickdeals">Slickdeals</option><option value="hip2save">hip2save</option></select></label>
        <label className="text-xs font-medium text-zinc-600">品牌<select name="brand" defaultValue={values.brand ?? ""} className={`mt-1 w-full ${inputClass}`}><option value="">全部</option>{brands.map((brand) => <option key={brand} value={brand}>{brand}</option>)}</select></label>
        <label className="text-xs font-medium text-zinc-600">类目<select name="category" defaultValue={values.category ?? ""} className={`mt-1 w-full ${inputClass}`}><option value="">全部</option>{categories.map((category) => <option key={category} value={category}>{category}</option>)}</select></label>
        <label className="text-xs font-medium text-zinc-600">Frontpage<select name="frontpage" defaultValue={values.frontpage ?? ""} className={`mt-1 w-full ${inputClass}`}><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
        <label className="text-xs font-medium text-zinc-600">最低价格<input name="price_min" type="number" min="0" step="0.01" defaultValue={values.price_min} className={`mt-1 w-full ${inputClass}`} /></label>
        <label className="text-xs font-medium text-zinc-600">最高价格<input name="price_max" type="number" min="0" step="0.01" defaultValue={values.price_max} className={`mt-1 w-full ${inputClass}`} /></label>
        <label className="text-xs font-medium text-zinc-600">最低折扣<input name="discount_min" type="number" min="0" max="100" step="1" defaultValue={values.discount_min} className={`mt-1 w-full ${inputClass}`} /></label>
        <label className="text-xs font-medium text-zinc-600">最高折扣<input name="discount_max" type="number" min="0" max="100" step="1" defaultValue={values.discount_max} className={`mt-1 w-full ${inputClass}`} /></label>
        <label className="text-xs font-medium text-zinc-600">反馈状态<select name="feedback" defaultValue={values.feedback ?? ""} className={`mt-1 w-full ${inputClass}`}><option value="">全部</option>{FEEDBACK_TYPES.map((type) => <option key={type} value={type}>{FEEDBACK_LABELS[type]}</option>)}<option value="unmarked">未标记</option></select></label>
        <label className="text-xs font-medium text-zinc-600">排序<select name="sort" defaultValue={values.sort ?? "time"} className={`mt-1 w-full ${inputClass}`}><option value="time">时间</option><option value="price">价格</option><option value="discount">折扣</option><option value="thumbs">点赞</option><option value="comments">评论</option></select></label>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-zinc-100 pt-4 text-sm text-zinc-700">
        {[ ["monitored", "只看监控品牌"], ["unknown", "只看未知品牌"], ["important", "只看重要 Deal"], ["false_positive", "只看误报"] ].map(([name, label]) => (
          <label key={name} className="inline-flex items-center gap-2"><input type="checkbox" name={name} value="1" defaultChecked={values[name] === "1"} className="h-4 w-4 rounded border-zinc-300 accent-emerald-700" />{label}</label>
        ))}
        <label className="ml-auto inline-flex items-center gap-2">顺序<select name="order" defaultValue={values.order ?? "desc"} className={inputClass}><option value="desc">降序</option><option value="asc">升序</option></select></label>
        <button type="submit" className="inline-flex h-9 items-center gap-2 rounded-md bg-zinc-900 px-4 text-sm font-medium text-white hover:bg-zinc-700"><Search className="h-4 w-4" />筛选</button>
        <Link href="/deals" className="inline-flex h-9 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium text-zinc-700 hover:bg-zinc-50"><RotateCcw className="h-4 w-4" />重置</Link>
      </div>
    </form>
  );
}
