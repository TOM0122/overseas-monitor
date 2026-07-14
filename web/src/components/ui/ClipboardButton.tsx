"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

export function ClipboardButton({ text, label = "复制", compact = false }: { text: string; label?: string; compact?: boolean }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }
  return (
    <button type="button" onClick={copy} title={label} className="inline-flex h-8 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border border-zinc-300 bg-white px-2.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 active:translate-y-px">
      {copied ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : <Copy className="h-3.5 w-3.5" aria-hidden="true" />}
      {compact ? <span className="sr-only">{copied ? "已复制" : label}</span> : copied ? "已复制" : label}
    </button>
  );
}
