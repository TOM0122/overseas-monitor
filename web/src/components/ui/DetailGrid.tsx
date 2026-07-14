import type { ReactNode } from "react";

export function DetailGrid({ items }: { items: Array<{ label: string; value: ReactNode }> }) {
  return (
    <dl className="grid rounded-md border border-zinc-200 bg-white sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="min-w-0 border-b border-zinc-100 px-4 py-3 sm:border-r xl:last:border-r-0">
          <dt className="text-xs text-zinc-500">{item.label}</dt>
          <dd className="mt-1 break-words text-sm font-medium text-zinc-900">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
