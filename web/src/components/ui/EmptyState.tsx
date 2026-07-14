import { Database } from "lucide-react";

export function EmptyState({ title = "暂无数据", description }: { title?: string; description?: string }) {
  return (
    <div className="rounded-md border border-dashed border-zinc-300 bg-white px-6 py-14 text-center">
      <Database className="mx-auto h-6 w-6 text-zinc-400" aria-hidden="true" />
      <p className="mt-3 text-sm font-medium text-zinc-800">{title}</p>
      {description ? <p className="mx-auto mt-1 max-w-xl text-sm text-zinc-500">{description}</p> : null}
    </div>
  );
}
