import type { ReactNode } from "react";

export function MetricCard({ label, value, detail, icon }: { label: string; value: ReactNode; detail?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="min-w-0 rounded-md border border-zinc-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3 text-sm text-zinc-500">
        <span>{label}</span>
        {icon ? <span className="text-zinc-400">{icon}</span> : null}
      </div>
      <div className="mt-2 truncate font-mono text-2xl font-semibold text-zinc-950">{value}</div>
      {detail ? <div className="mt-1 truncate text-xs text-zinc-500">{detail}</div> : null}
    </div>
  );
}
