import { useInfiniteQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { Search, Users } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LoadMore } from "@/components/load-more";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { maskPhone } from "@/features/profile/mask";
import { formatKst } from "@/lib/datetime";
import { useDebounced } from "@/lib/use-debounced";
import { cn } from "@/lib/utils";

import { ACCOUNT_TYPE_LABELS, membersQuery, type Member, type MemberTab } from "../api";
import { MemberSheet } from "./member-sheet";

export interface MembersSearch {
  tab?: MemberTab;
  q?: string;
  status?: "active" | "inactive";
  user?: string;
}

const TABS: { value: MemberTab | undefined; label: string; count: "ALL" | "STUDENT" | "MENTOR" | "STAFF" }[] = [
  { value: undefined, label: "전체", count: "ALL" },
  { value: "student", label: "수강생", count: "STUDENT" },
  { value: "mentor", label: "멘토", count: "MENTOR" },
  { value: "staff", label: "운영진", count: "STAFF" },
];
const ALL_STATUS = "all";
const COLUMNS = "grid grid-cols-[minmax(0,1.3fr)_minmax(0,1.7fr)_120px_72px_88px_112px_64px] items-center gap-3";

/** 날짜 표시: 'yy.MM.dd' */
const day = (value: string | null | undefined) => (value ? formatKst(value, "yy.MM.dd") : "—");

/** 회원 관리 > 전체 회원 (F71): 승인된 계정 목록 + 슬라이드 패널 */
export function MembersPage({ search }: { search: MembersSearch }) {
  const navigate = useNavigate();
  const filter = { tab: search.tab, q: search.q, status: search.status };
  const list = useInfiniteQuery(membersQuery(filter));
  const [q, setQ] = useState(search.q ?? "");
  const debounced = useDebounced(q.trim());
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const counts = list.data?.pages[0]?.counts;
  const go = (next: MembersSearch) => void navigate({ to: "/admin/members/users", search: next });

  // 검색어는 입력이 멈추면 주소에 반영한다
  useEffect(() => {
    if ((search.q ?? "") === debounced) return;
    void navigate({
      to: "/admin/members/users",
      search: { ...search, q: debounced || undefined, user: undefined },
      replace: true,
    });
  }, [debounced, search, navigate]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">전체 회원</h1>
        <p className="text-body text-muted-foreground">승인된 계정을 보고, 계정을 비활성화하거나 다시 활성화해요.</p>
      </div>
      <div className="flex items-end gap-3">
        <nav aria-label="계정 종류" className="flex-1">
          <ul className="flex gap-1 border-b border-border">
            {TABS.map((t) => {
              const active = t.value === search.tab;
              const count = counts?.[t.count];
              return (
                <li key={t.label}>
                  <Link
                    to="/admin/members/users"
                    search={{ ...(t.value ? { tab: t.value } : {}), q: search.q, status: search.status }}
                    aria-current={active ? "page" : undefined}
                    aria-label={count === undefined ? t.label : `${t.label} ${count}`}
                    className={cn(
                      "-mb-px inline-flex h-10 items-center gap-1.5 border-b-2 px-3 text-body outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      active
                        ? "border-primary text-primary-text"
                        : "border-transparent text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {t.label}
                    {count === undefined ? null : <span>· {count}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="relative w-60">
          <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="회원 검색"
            placeholder="이름·이메일·휴대폰 검색"
            value={q}
            maxLength={50}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select
          value={search.status ?? ALL_STATUS}
          onValueChange={(v) =>
            go({ ...search, status: v === ALL_STATUS ? undefined : (v as "active" | "inactive"), user: undefined })
          }
        >
          <SelectTrigger aria-label="상태" className="w-35">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_STATUS}>모든 상태</SelectItem>
            <SelectItem value="active">활성</SelectItem>
            <SelectItem value="inactive">비활성</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {list.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : list.isError ? (
        <ErrorState onRetry={() => void list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Users}
          title={search.q || search.status ? "찾는 회원이 없어요" : "회원이 없어요"}
          {...(search.q ? { description: "이름·이메일·휴대폰을 다시 확인해 주세요." } : {})}
        />
      ) : (
        <div
          role="table"
          aria-label="회원"
          className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm"
        >
          <div role="row" className={cn(COLUMNS, "bg-muted px-4 py-2.5 text-caption text-muted-foreground")}>
            {["이름", "이메일", "휴대폰", "종류", "승인일", "마지막 로그인", "상태"].map((h) => (
              <span key={h} role="columnheader">
                {h}
              </span>
            ))}
          </div>
          {items.map((m) => (
            <MemberRow key={m.id} member={m} search={search} selected={m.id === search.user} />
          ))}
        </div>
      )}
      {list.hasNextPage ? (
        <LoadMore
          loading={list.isFetchingNextPage}
          label="다음 회원을 불러오는 중…"
          onVisible={() => void list.fetchNextPage()}
        />
      ) : null}
      {search.user ? (
        <MemberSheet key={search.user} userId={search.user} onClose={() => go({ ...search, user: undefined })} />
      ) : null}
    </div>
  );
}

function MemberRow({ member: m, search, selected }: { member: Member; search: MembersSearch; selected: boolean }) {
  return (
    <div
      role="row"
      aria-label={m.name}
      className={cn(COLUMNS, "relative border-t border-border px-4 py-3 hover:bg-accent/60", selected && "bg-accent")}
    >
      <span role="cell" className="flex min-w-0 items-center gap-1.5">
        <Link
          to="/admin/members/users"
          search={{ ...search, user: m.id }}
          className={cn(
            "truncate text-body-strong after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring",
            m.is_active ? "text-foreground" : "text-muted-foreground",
            selected && "text-primary",
          )}
        >
          {m.name}
        </Link>
        {m.is_super_admin ? <Badge variant="primary">최고 관리자</Badge> : null}
      </span>
      <span role="cell" className="truncate text-body text-muted-foreground">
        {m.email}
      </span>
      <span role="cell" className="text-body text-muted-foreground">
        {maskPhone(m.phone_number) ?? "—"}
      </span>
      <span role="cell" className="text-body text-foreground">
        {ACCOUNT_TYPE_LABELS[m.account_type]}
      </span>
      <span role="cell" className="text-body text-foreground">
        {day(m.approved_at)}
      </span>
      <span role="cell" className="text-body text-muted-foreground">
        {m.last_login_at ? formatKst(m.last_login_at, "M/d HH:mm") : "—"}
      </span>
      <span role="cell">
        <Badge variant={m.is_active ? "success" : "secondary"}>{m.is_active ? "활성" : "비활성"}</Badge>
      </span>
    </div>
  );
}
