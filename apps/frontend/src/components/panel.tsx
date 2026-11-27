import { X, type LucideIcon } from "lucide-react";
import { useId, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/ui/help-tip";
import { SheetDescription, SheetTitle } from "@/components/ui/sheet";

/**
 * 슬라이드 패널 부품 (F68, 모양은 F92): 머리, 섹션(둥근 카드 + 보라 띠 제목), '라벨 | 값' 줄, 한 줄에 하나인 목록.
 * `Sheet`/`SheetContent` 안에서 쓴다.
 */
export function PanelHead({
  title,
  description,
  badges,
  actions,
  onClose,
}: {
  title: string;
  description: string;
  badges?: ReactNode;
  actions?: ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="flex items-start gap-3 border-b border-border bg-linear-to-b from-sidebar-accent/50 to-card py-5 pr-4 pl-6">
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <SheetTitle className="text-h2 text-foreground">{title}</SheetTitle>
          {badges}
        </div>
        <SheetDescription className="truncate text-body text-muted-foreground">{description}</SheetDescription>
      </div>
      {actions}
      <Button variant="ghost" size="sm" aria-label="닫기" className="px-2" onClick={onClose}>
        <X />
      </Button>
    </div>
  );
}

export function PanelSection({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  /** 제목 앞 아이콘 (없으면 보라 띠) */
  icon?: LucideIcon;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      className="shrink-0 overflow-hidden rounded-xl border border-border bg-card shadow-sm"
    >
      <h3
        id={id}
        className="flex items-center gap-2 border-b border-border/70 px-4 pt-3 pb-2.5 text-body-strong text-foreground"
      >
        {Icon ? (
          <span
            aria-hidden
            className="inline-flex size-6 items-center justify-center rounded-md bg-primary/12 text-primary-text"
          >
            <Icon className="size-3.5" />
          </span>
        ) : (
          <span aria-hidden className="h-3.5 w-1 rounded-full bg-primary" />
        )}
        {title}
      </h3>
      <div className="flex flex-col gap-3 px-4 py-3.5">{children}</div>
    </section>
  );
}

/** '라벨 | 값' 한 줄. 설명은 라벨 옆 `?`로 */
export function PanelRow({
  label,
  children,
  htmlFor,
  help,
  top = false,
}: {
  label: string;
  children: ReactNode;
  htmlFor?: string;
  help?: string;
  /** 값이 여러 줄이면 라벨을 위에 맞춘다 */
  top?: boolean;
}) {
  return (
    <div className={`grid grid-cols-[96px_minmax(0,1fr)] gap-3 ${top ? "items-start" : "items-center"}`}>
      <span className={`flex items-center gap-1 ${top ? "min-h-9" : ""}`}>
        {htmlFor ? (
          <label htmlFor={htmlFor} className="text-body text-muted-foreground">
            {label}
          </label>
        ) : (
          <span className="text-body text-muted-foreground">{label}</span>
        )}
        {help ? <HelpTip label={label}>{help}</HelpTip> : null}
      </span>
      <div className="min-w-0 text-body-strong text-foreground">{children}</div>
    </div>
  );
}

/** 한 줄에 하나인 목록. `onRemove`가 있으면 줄마다 빼기 */
export function PanelList({
  label,
  items,
  onRemove,
}: {
  label: string;
  items: { id: string; name: string; meta?: string }[];
  onRemove?: (id: string) => void;
}) {
  return (
    <ul aria-label={label} className="divide-y divide-border overflow-hidden rounded-md border border-border">
      {items.map((item) => (
        <li key={item.id} className="flex min-h-10 items-center gap-2 py-1.5 pr-1.5 pl-3">
          <span className="min-w-0 flex-1 truncate text-body text-foreground">{item.name}</span>
          {item.meta ? <span className="pr-1.5 text-caption text-muted-foreground">{item.meta}</span> : null}
          {onRemove ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-label={`${item.name} 빼기`}
              className="px-2"
              onClick={() => onRemove(item.id)}
            >
              <X />
            </Button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

/** 조회 머리의 [수정] [삭제] (F68: 삭제는 수정 모드에 넣지 않는다) */
export function PanelActions({ onEdit, onDelete }: { onEdit: () => void; onDelete?: () => void }) {
  return (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={onEdit}>
        수정
      </Button>
      {onDelete ? (
        <Button
          variant="outline"
          size="sm"
          className="border-destructive-text text-destructive-text hover:bg-destructive-subtle hover:text-destructive-text"
          onClick={onDelete}
        >
          삭제
        </Button>
      ) : null}
    </div>
  );
}
