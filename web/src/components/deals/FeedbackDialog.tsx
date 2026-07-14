"use client";

import { MessageSquarePlus, X } from "lucide-react";
import { useActionState, useEffect, useRef } from "react";

import { createDealFeedback, initialFeedbackState } from "@/app/actions/feedback";
import { FEEDBACK_LABELS } from "@/lib/format";
import { FEEDBACK_TYPES } from "@/lib/types";

export function FeedbackDialog({ dealId, title }: { dealId: string; title: string }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [state, formAction, pending] = useActionState(createDealFeedback, initialFeedbackState);

  useEffect(() => {
    if (!state.ok) return;
    const timer = window.setTimeout(() => dialogRef.current?.close(), 700);
    return () => window.clearTimeout(timer);
  }, [state]);

  return (
    <>
      <button type="button" onClick={() => dialogRef.current?.showModal()} className="inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-md bg-zinc-900 px-2.5 text-xs font-medium text-white hover:bg-zinc-700 active:translate-y-px">
        <MessageSquarePlus className="h-3.5 w-3.5" aria-hidden="true" />
        标记反馈
      </button>
      <dialog ref={dialogRef} className="m-auto w-[min(92vw,520px)] rounded-md border border-zinc-200 bg-white p-0 text-zinc-950 shadow-2xl backdrop:bg-zinc-950/30">
        <div className="flex items-start justify-between border-b border-zinc-200 px-5 py-4">
          <div><h2 className="text-base font-semibold">标记 Deal 反馈</h2><p className="mt-1 line-clamp-2 text-sm text-zinc-500">{title}</p></div>
          <button type="button" onClick={() => dialogRef.current?.close()} aria-label="关闭" title="关闭" className="inline-flex h-8 w-8 items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100"><X className="h-4 w-4" /></button>
        </div>
        <form action={formAction} className="space-y-4 p-5">
          <input type="hidden" name="deal_id" value={dealId} />
          <label className="block text-sm font-medium text-zinc-700">反馈类型
            <select name="feedback_type" required defaultValue="valid" className="mt-1.5 h-10 w-full rounded-md border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100">
              {FEEDBACK_TYPES.map((type) => <option key={type} value={type}>{FEEDBACK_LABELS[type]}</option>)}
            </select>
          </label>
          <label className="block text-sm font-medium text-zinc-700">原因
            <input name="reason" maxLength={300} placeholder="例如：标题含粉丝语境，非风扇产品" className="mt-1.5 h-10 w-full rounded-md border border-zinc-300 px-3 text-sm outline-none placeholder:text-zinc-400 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100" />
          </label>
          <label className="block text-sm font-medium text-zinc-700">备注
            <textarea name="note" maxLength={1000} rows={4} placeholder="补充人工判断或后续动作" className="mt-1.5 w-full resize-y rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none placeholder:text-zinc-400 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100" />
          </label>
          {state.message ? <p className={`text-sm ${state.ok ? "text-emerald-700" : "text-red-700"}`} role="status">{state.message}</p> : null}
          <div className="flex justify-end gap-2 border-t border-zinc-100 pt-4">
            <button type="button" onClick={() => dialogRef.current?.close()} className="h-9 rounded-md border border-zinc-300 bg-white px-4 text-sm font-medium text-zinc-700 hover:bg-zinc-50">取消</button>
            <button type="submit" disabled={pending} className="h-9 rounded-md bg-emerald-700 px-4 text-sm font-medium text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60">{pending ? "提交中" : "提交"}</button>
          </div>
        </form>
      </dialog>
    </>
  );
}
