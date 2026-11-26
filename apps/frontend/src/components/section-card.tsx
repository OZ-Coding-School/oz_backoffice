import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { HelpTip } from "@/components/ui/help-tip";
import { cn } from "@/lib/utils";

/**
 * 섹션 카드 (F91·F92): 아이콘 배지 + 제목·한 줄 설명, 오른쪽 동작.
 * `rows`면 안쪽을 구분선 줄(`SettingRow`)로, 아니면 여백을 두고 그대로 그린다.
 */
export function SectionCard({
  icon: Icon,
  title,
  description,
  help,
  action,
  rows = false,
  className,
  bodyClassName,
  children,
}: {
  icon?: LucideIcon;
  title: string;
  description?: ReactNode;
  help?: string;
  action?: ReactNode;
  rows?: boolean;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <section
      aria-label={title}
      className={cn("overflow-hidden rounded-2xl border border-border bg-card shadow-sm", className)}
    >
      <div className="flex items-center gap-3 px-5 pt-4 pb-3.5 md:px-6 md:pt-5 md:pb-4">
        {Icon ? (
          <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-sidebar-accent text-sidebar-accent-foreground">
            <Icon aria-hidden className="size-4.5" />
          </span>
        ) : null}
        <div className="flex min-w-0 flex-1 flex-col">
          <h2 className="flex items-center gap-1.5 text-h3 text-foreground">
            {title}
            {help ? <HelpTip label={title}>{help}</HelpTip> : null}
          </h2>
          {description ? <p className="text-body-sm text-muted-foreground">{description}</p> : null}
        </div>
        {action}
      </div>
      <div
        className={cn(
          "border-t border-border",
          rows ? "flex flex-col divide-y divide-border" : "flex flex-col gap-4 p-5 md:p-6",
          bodyClassName,
        )}
      >
        {children}
      </div>
    </section>
  );
}

/** 설정 한 줄: 왼쪽 이름·짧은 설명 | 오른쪽 조작 (F91) */
export function SettingRow({
  title,
  description,
  error,
  children,
}: {
  title: string;
  description?: ReactNode;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-5 py-4 md:px-6">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-body-strong text-foreground">{title}</span>
        {description ? <span className="text-body-sm text-muted-foreground">{description}</span> : null}
        {error ? <span className="text-caption text-destructive-text">{error}</span> : null}
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}
