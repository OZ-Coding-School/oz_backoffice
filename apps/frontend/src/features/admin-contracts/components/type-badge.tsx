import { AppWindow, GraduationCap, Laptop, Package, UserRound, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

import type { ContractType } from "../api";
import { TYPE_LABELS } from "../labels";

/**
 * 계약 종류 배지 (F96 보완): 상태 배지(둥근 알약, F14 상태 색)와 섞이지 않게 둥근 사각 + 아이콘.
 * 사람 계약(멘토·강사)은 브랜드 보라 계열, 업체 계약(SW·장비·기타)은 중립 계열.
 */
const TYPE_STYLE: Record<ContractType, { icon: LucideIcon; className: string }> = {
  MENTOR: { icon: UserRound, className: "bg-primary/12 text-primary-text" },
  INSTRUCTOR: { icon: GraduationCap, className: "bg-sidebar-accent text-sidebar-accent-foreground" },
  SW: { icon: AppWindow, className: "bg-secondary text-secondary-foreground" },
  EQUIPMENT: { icon: Laptop, className: "bg-muted text-foreground" },
  OTHER: { icon: Package, className: "border border-border bg-card text-muted-foreground" },
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

/** 이름 칸 앞 표시: 사람은 이름 첫 글자 원, 업체는 종류 아이콘 사각 */
export function PartyMark({ type, name }: { type: ContractType; name: string }) {
  if (type === "MENTOR" || type === "INSTRUCTOR")
    return (
      <span
        aria-hidden
        className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-label text-accent-foreground"
      >
        {name.slice(0, 1)}
      </span>
    );
  const { icon: Icon } = TYPE_STYLE[type];
  return (
    <span
      aria-hidden
      className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground"
    >
      <Icon className="size-4" />
    </span>
  );
}
