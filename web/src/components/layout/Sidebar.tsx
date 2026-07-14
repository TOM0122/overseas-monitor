"use client";

import { Activity, FileText, LayoutDashboard, Menu, Tags, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/runs", label: "运行记录", icon: Activity },
  { href: "/deals", label: "Deal 复核", icon: Tags },
  { href: "/reports", label: "报告历史", icon: FileText },
];

function NavContent({ close }: { close?: () => void }) {
  const pathname = usePathname();
  return (
    <>
      <div className="border-b border-zinc-200 px-5 py-5">
        <div className="text-sm font-semibold text-zinc-950">Overseas Monitor</div>
        <div className="mt-1 text-xs text-zinc-500">站外竞品情报控制台</div>
      </div>
      <nav className="flex-1 space-y-1 p-3" aria-label="主导航">
        {NAV_ITEMS.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link key={item.href} href={item.href} onClick={close} className={`flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium ${active ? "bg-emerald-50 text-emerald-900" : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950"}`}>
              <Icon className="h-4 w-4" strokeWidth={1.8} aria-hidden="true" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-zinc-200 px-5 py-4 text-xs leading-5 text-zinc-500">数据由 Railway Agent 每日更新</div>
    </>
  );
}

export function Sidebar() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r border-zinc-200 bg-white lg:flex"><NavContent /></aside>
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-zinc-200 bg-white px-4 lg:hidden">
        <div><div className="text-sm font-semibold text-zinc-950">Overseas Monitor</div><div className="text-[11px] text-zinc-500">竞品情报控制台</div></div>
        <button type="button" onClick={() => setOpen(true)} aria-label="打开导航" title="打开导航" className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-zinc-300 bg-white text-zinc-700"><Menu className="h-4 w-4" /></button>
      </header>
      {open ? (
        <div className="fixed inset-0 z-30 lg:hidden">
          <button type="button" className="absolute inset-0 bg-zinc-950/25" onClick={() => setOpen(false)} aria-label="关闭导航遮罩" />
          <aside className="relative flex h-full w-72 flex-col border-r border-zinc-200 bg-white shadow-xl">
            <button type="button" onClick={() => setOpen(false)} aria-label="关闭导航" title="关闭导航" className="absolute right-3 top-3 inline-flex h-8 w-8 items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100"><X className="h-4 w-4" /></button>
            <NavContent close={() => setOpen(false)} />
          </aside>
        </div>
      ) : null}
    </>
  );
}
