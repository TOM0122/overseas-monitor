import type { ReactNode } from "react";

export interface DataColumn<T> {
  key: string;
  header: string;
  className?: string;
  render: (row: T) => ReactNode;
}

export function DataTable<T>({ columns, rows, rowKey, emptyText = "暂无数据" }: {
  columns: DataColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  emptyText?: string;
}) {
  return (
    <div className="overflow-x-auto rounded-md border border-zinc-200 bg-white">
      <table className="w-full min-w-max border-collapse text-left text-sm">
        <thead className="bg-zinc-50 text-xs font-medium text-zinc-600">
          <tr>{columns.map((column) => <th key={column.key} className={`border-b border-zinc-200 px-3 py-2.5 ${column.className ?? ""}`}>{column.header}</th>)}</tr>
        </thead>
        <tbody className="text-zinc-700">
          {rows.length ? rows.map((row) => (
            <tr key={rowKey(row)} className="align-top hover:bg-zinc-50/70">
              {columns.map((column) => <td key={column.key} className={`border-b border-zinc-100 px-3 py-3 last:border-b-0 ${column.className ?? ""}`}>{column.render(row)}</td>)}
            </tr>
          )) : (
            <tr><td colSpan={columns.length} className="px-4 py-12 text-center text-zinc-500">{emptyText}</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
