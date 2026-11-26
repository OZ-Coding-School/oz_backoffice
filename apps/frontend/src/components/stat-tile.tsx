import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** 요약 숫자 칸 (F92): 아이콘 칩 · 이름, 큰 값, 아래 한 줄 */
export function StatTile({
  icon: Icon,
  label,
  value,
  hint,
  valueClassName,
}: {
  icon?: LucideIcon;
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  valueClassName?: string;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-4 shadow-sm">
      <span className="flex items-center gap-2 text-caption text-muted-foreground">
        {Icon ? (
          <span className="inline-flex size-6 items-center justify-center rounded-lg bg-sidebar-accent text-sidebar-accent-foreground">
            <Icon aria-hidden className="size-3.5" />
          </span>
        ) : null}
        {label}
      </span>
      <span className={cn("text-h2 text-foreground", valueClassName)}>{value}</span>
      {hint ? <span className="text-caption text-muted-foreground">{hint}</span> : null}
    </div>
  );
}
