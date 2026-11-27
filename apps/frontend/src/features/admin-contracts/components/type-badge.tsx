import { AppWindow, GraduationCap, Laptop, Package, UserRound, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

import type { ContractType } from "../api";
import { TYPE_LABELS } from "../labels";

/**
 * 계약 종류 배지 (F96 보완): 상태 배지(둥근 알약)와 섞이지 않게 둥근 사각 + 아이콘, 종류마다 다른 색.
 */
const TYPE_STYLE: Record<ContractType, { icon: LucideIcon; className: string }> = {
  MENTOR: { icon: UserRound, className: "bg-primary/15 text-primary-text" },
  INSTRUCTOR: { icon: GraduationCap, className: "bg-info/15 text-info-text" },
  SW: { icon: AppWindow, className: "bg-success/15 text-success-text" },
  EQUIPMENT: { icon: Laptop, className: "bg-warning/20 text-warning-text" },
  OTHER: { icon: Package, className: "bg-muted-foreground/15 text-foreground" },
};

export function ContractTypeBadge({ type, className }: { type: ContractType; className?: string }) {
  const { icon: Icon, className: tone } = TYPE_STYLE[type];
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-caption-strong whitespace-nowrap",
        tone,
        className,
      )}
    >
      <Icon aria-hidden className="size-3.5" />
      {TYPE_LABELS[type]}
    </span>
  );
}
