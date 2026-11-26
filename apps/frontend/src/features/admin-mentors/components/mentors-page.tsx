import { useInfiniteQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { Search, UserRound } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LoadMore } from "@/components/load-more";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { maskPhone } from "@/features/profile/mask";
import { useDebounced } from "@/lib/use-debounced";
import { cn } from "@/lib/utils";

import { mentorsQuery, type MentorItem } from "../api";

export type MentorStatus = "active" | "inactive" | "pending";

export interface MentorsSearch {
  q?: string;
  status?: MentorStatus;
}

const ALL_STATUS = "all";
// 칸 폭을 고정해 넓은 화면에서도 칸 사이가 벌어지지 않게 하고, 남는 폭은 마지막 칸(상태)이 받는다
const COLUMNS = "grid grid-cols-[200px_260px_140px_64px_120px_minmax(0,1fr)] items-center gap-4";

/** 강사·멘토 > 멘토 (F79·F80): 검색·상태 + 표(항목마다 칸), 행을 누르면 상세 페이지 */
export function MentorsPage({ search }: { search: MentorsSearch }) {
  const navigate = useNavigate();
  const list = useInfiniteQuery(mentorsQuery({ q: search.q, status: search.status }));
  const [q, setQ] = useState(search.q ?? "");
  const debounced = useDebounced(q.trim());
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];

  // 검색어는 입력이 멈추면 주소에 반영한다
  useEffect(() => {
    if ((search.q ?? "") === debounced) return;
    void navigate({ to: "/admin/educators/mentors", search: { ...search, q: debounced || undefined }, replace: true });
  }, [debounced, search, navigate]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">멘토</h1>
        <p className="text-body text-muted-foreground">가입한 멘토의 프로필·배정·계약을 관리해요.</p>
      </div>
      <div className="flex items-center justify-between gap-3">
        <Select
          value={search.status ?? ALL_STATUS}
          onValueChange={(v) =>
            void navigate({
              to: "/admin/educators/mentors",
              search: { ...search, status: v === ALL_STATUS ? undefined : (v as MentorStatus) },
            })
          }
        >
          <SelectTrigger aria-label="상태" className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_STATUS}>모든 상태</SelectItem>
            <SelectItem value="active">활성</SelectItem>
            <SelectItem value="inactive">비활성</SelectItem>
            <SelectItem value="pending">가입 전</SelectItem>
          </SelectContent>
        </Select>
        <div className="relative w-65">
          <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="멘토 검색"
            placeholder="이름·이메일·휴대폰·닉네임 검색"
            value={q}
            maxLength={50}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>
      {list.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : list.isError ? (
        <ErrorState onRetry={() => void list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={UserRound}
          title={search.q || search.status ? "찾는 멘토가 없어요" : "가입한 멘토가 없어요"}
          {...(search.q ? { description: "이름·이메일·휴대폰·닉네임을 다시 확인해 주세요." } : {})}
        />
      ) : (
        <div className="flex flex-col gap-3">
          <div
            role="table"
            aria-label="멘토"
            className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm"
          >
            <div role="row" className={cn(COLUMNS, "bg-muted px-4 py-2.5 text-caption text-muted-foreground")}>
              {["이름(닉네임)", "이메일", "휴대폰", "계약", "신청 받기", "상태"].map((h) => (
                <span key={h} role="columnheader">
                  {h}
                </span>
              ))}
            </div>
            {items.map((m) => (
              <MentorRow key={m.id} mentor={m} />
            ))}
          </div>
          <p className="text-caption text-muted-foreground">
            괄호 안은 수강생에게 보이는 닉네임이에요. 가입 전 멘토는 계약을 먼저 만든 멘토로, 가입하면 계정이 연결돼요.
          </p>
        </div>
      )}
      {list.hasNextPage ? (
        <LoadMore
          loading={list.isFetchingNextPage}
          label="다음 멘토를 불러오는 중…"
          onVisible={() => void list.fetchNextPage()}
        />
      ) : null}
    </div>
  );
}

function MentorRow({ mentor: m }: { mentor: MentorItem }) {
  const shown = m.display_name && m.display_name !== m.name ? m.display_name : null;
  return (
    <div
      role="row"
      aria-label={m.name}
      className={cn(COLUMNS, "relative border-t border-border px-4 py-3 hover:bg-accent/60")}
    >
      <span role="cell" className="min-w-0 truncate">
        <Link
          to="/admin/educators/mentors/$mentorId"
          params={{ mentorId: m.id }}
          className={cn(
            "text-body-strong after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring",
            m.is_active ? "text-foreground" : "text-muted-foreground",
          )}
        >
          {m.name}
          {shown ? `(${shown})` : ""}
        </Link>
      </span>
      <span role="cell" className="truncate text-body text-foreground">
        {m.email ?? "—"}
      </span>
      <span role="cell" className="text-body text-foreground">
        {maskPhone(m.phone_number) ?? "—"}
      </span>
      <span role="cell" className="text-body text-foreground">
        {m.contract_count}건
      </span>
      <span role="cell">
        <AcceptingBadge on={m.accepting_requests} />
      </span>
      <span role="cell">
        <StatusBadge mentor={m} />
      </span>
    </div>
  );
}

export function AcceptingBadge({ on }: { on: boolean }) {
  return <Badge variant={on ? "info" : "outline"}>{on ? "신청 받는 중" : "신청 꺼짐"}</Badge>;
}

/** 활성 · 비활성 · 가입 전(A104) */
export function StatusBadge({ mentor: m }: { mentor: Pick<MentorItem, "is_active" | "is_registered"> }) {
  if (!m.is_registered) return <Badge variant="warning">가입 전</Badge>;
  return <Badge variant={m.is_active ? "success" : "secondary"}>{m.is_active ? "활성" : "비활성"}</Badge>;
}
