import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * 공통 빈 상태 (Figma `Components / Empty State`, decisions F27).
 * 목록·홈 등이 비어 있을 때 아이콘 · 제목 · 설명을 점선 상자 안에 보여 준다.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description?: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "flex flex-col items-center gap-3 rounded-xl border border-dashed border-border bg-card px-6 py-10 text-center",
        className,
      )}
    >
      <span aria-hidden className="inline-flex size-12 items-center justify-center rounded-full bg-accent">
        <Icon className="size-6 text-accent-foreground" />
      </span>
      <h2 className="text-h3 text-foreground">{title}</h2>
      {description ? <p className="text-body-sm text-muted-foreground">{description}</p> : null}
    </section>
  );
}
