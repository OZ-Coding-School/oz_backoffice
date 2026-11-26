import type { ReactNode } from "react";

import { Avatar } from "@/components/ui/avatar";

/**
 * 상세 화면 머리 (F92): 파스텔 그라데이션 카드에 큰 아바타 · 이름 + 배지 · 한 줄 정보, 오른쪽 동작.
 * 사람(수강생·멘토) 상세가 같이 쓴다.
 */
export function ProfileHero({
  name,
  avatar,
  badges,
  description,
  actions,
}: {
  name: string;
  /** 사진 등 (없으면 이름 첫 글자) */
  avatar?: ReactNode;
  badges?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-primary/15 bg-linear-to-br from-sidebar-accent via-card to-card p-5 shadow-sm">
      {avatar ?? <Avatar name={name} className="size-14 text-h2 ring-4 ring-card" />}
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-h1 text-foreground">{name}</h1>
          {badges}
        </div>
        {description ? <p className="truncate text-body text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
