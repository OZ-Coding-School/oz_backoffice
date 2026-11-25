import { ChevronDown, ChevronRight } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

/**
 * 접고 펼치는 종류별 상자 (F69). 머리글: 펼침 화살표 · 앞 표시(아이콘 등) · 이름 · 건수.
 * 확인 창의 영향 목록·바뀐 권한에 쓰고, 처음에는 접어 둔다.
 */
export function CollapsibleGroup({
  title,
  count,
  leading,
  children,
  defaultOpen = false,
}: {
  title: string;
  count: string;
  leading?: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <section className="shrink-0 overflow-hidden rounded-lg border border-border bg-card">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 bg-muted px-3 py-2.5 text-left hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        {open ? (
          <ChevronDown aria-hidden className="size-4 shrink-0" />
        ) : (
          <ChevronRight aria-hidden className="size-4 shrink-0" />
        )}
        {leading}
        <span className="flex-1 text-body-strong text-foreground">{title}</span>
        <span className="text-caption-strong text-muted-foreground">{count}</span>
      </button>
      {open ? (
        <ul id={id} aria-label={title} className="border-t border-border py-1">
          {children}
        </ul>
      ) : null}
    </section>
  );
}

/** 상자 안 한 줄: 이름 · 보조 정보 · (배지) */
export function GroupItem({ main, sub, badge }: { main: string; sub?: string; badge?: ReactNode }) {
  return (
    <li className="flex min-h-9 items-center gap-2 py-1.5 pr-3 pl-10">
      <span className="shrink-0 text-body-strong text-foreground">{main}</span>
      {sub ? <span className="min-w-0 flex-1 truncate text-caption text-muted-foreground">{sub}</span> : null}
      {badge ? <span className={sub ? "" : "ml-auto"}>{badge}</span> : null}
    </li>
  );
}
