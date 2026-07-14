"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { ClipboardButton } from "@/components/ui/ClipboardButton";

export function MarkdownReportViewer({ markdown }: { markdown: string }) {
  return (
    <section className="rounded-md border border-zinc-200 bg-white">
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-zinc-900">报告 Markdown</h2>
        <ClipboardButton text={markdown} label="复制 Markdown" />
      </div>
      <article className="report-markdown max-w-none px-5 py-6 sm:px-7">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
      </article>
    </section>
  );
}
