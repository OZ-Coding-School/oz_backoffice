import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/**
 * 페이지 머리 (F91·F92): 제목 · 아래 줄에 기수 같은 칩과 상태 · 설명, 오른쪽에 동작.
 * 운영진·수강생·멘토 화면이 같은 모양을 쓴다.
 */
export function PageHeader({
  icon: Icon,
  title,
  description,
  meta,
  actions,
  hideTitle = false,
}: {
  /** 제목 왼쪽 아이콘 타일 (메뉴 아이콘과 같은 것) */
  icon?: LucideIcon;
  title: string;
  description?: ReactNode;
  /** 제목 아래 줄: `<MetaChip>`·상태 표시 */
  meta?: ReactNode;
  actions?: ReactNode;
  /** 틀이 제목을 대신 보여 줄 때 (화면 안에 끼운 경우) */
  hideTitle?: boolean;
}) {
  return (
    <header className="flex flex-wrap items-start gap-4">
      {Icon && !hideTitle ? (
        <span className="hidden size-12 shrink-0 items-center justify-center rounded-2xl bg-linear-to-br from-primary to-primary/70 text-primary-foreground shadow-md md:inline-flex">
          <Icon aria-hidden className="size-6" />
        </span>
      ) : null}
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        {hideTitle ? null : <h1 className="text-h1 text-foreground">{title}</h1>}
        {meta ? (
          <div className="flex flex-wrap items-center gap-2 text-body-sm text-muted-foreground">{meta}</div>
        ) : null}
        {description ? <p className="text-body text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

/** 머리 아래 줄의 파스텔 칩 (기수 이름 등) */
export function MetaChip({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full bg-sidebar-accent px-2.5 py-0.5 text-caption-strong text-sidebar-accent-foreground">
      {children}
    </span>
  );
}
