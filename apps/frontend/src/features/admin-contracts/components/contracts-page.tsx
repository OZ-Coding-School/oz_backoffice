import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { FileSignature, FileText, Plus, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LoadMore } from "@/components/load-more";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { hasPermission, staffAccessQuery, type StaffCohort } from "@/features/staff/api";
import { pickableCohorts, rememberedAdminScope } from "@/features/staff/current-cohort";
import { formatKst } from "@/lib/datetime";
import { useDebounced } from "@/lib/use-debounced";
import { cn } from "@/lib/utils";

import { contractsQuery, type Contract, type ContractType, type StatusGroup } from "../api";
import { academyText, amountSub, amountText, period, periodHint, STATUS, TYPE_LABELS, TYPES } from "../labels";
import { ContractSheet } from "./contract-sheet";
import { ContractTypeBadge } from "./type-badge";

export interface ContractsSearch {
  /** 과정 전체 */
  bootcamp?: string;
  /** 기수 (그 기수 + 과정 공통) */
  cohort?: string;
  /** 상태 묶음 (없으면 진행 중인 계약) */
  status?: StatusGroup;
  type?: ContractType;
  q?: string;
  /** 패널: 계약 id 또는 new */
  contract?: string;
}

const GROUP_LABELS: Record<StatusGroup, string> = {
  open: "진행 중인 계약",
  closed: "끝난 계약",
  all: "전체 상태",
};
const COLUMNS =
  "grid grid-cols-[minmax(0,1.3fr)_72px_minmax(0,1.1fr)_188px_164px_minmax(0,1fr)_76px_64px] items-center gap-4";

/** 처음 고를 범위: 이 화면에서 마지막으로 고른 과정·기수 → 진행 중인 첫 기수 → 첫 기수 (F96) */
function initialScope(cohorts: readonly StaffCohort[]): { bootcamp?: string; cohort?: string } | null {
  const list = pickableCohorts(cohorts);
  const remembered = rememberedAdminScope();
  if (remembered?.cohort && list.some((c) => c.id === remembered.cohort)) return { cohort: remembered.cohort };
  if (remembered?.bootcamp && list.some((c) => c.bootcamp_id === remembered.bootcamp))
    return { bootcamp: remembered.bootcamp };
  const first = list.find((c) => c.status === "ONGOING") ?? list[0];
  return first ? { cohort: first.id } : null;
}

/** 행정 업무 > 계약 (F83·F96): 상단 과정·기수, 종류 탭(건수) · 상태 · 검색 + 표, 행을 누르면 오른쪽 패널 */
export function ContractsPage({ search }: { search: ContractsSearch }) {
  const navigate = useNavigate();
  const access = useQuery(staffAccessQuery);
  const canManage = !!access.data && hasPermission(access.data, "educator.contract.manage");
  const cohorts = access.data?.cohorts ?? [];
  const scoped = !!(search.cohort || search.bootcamp);
  const list = useInfiniteQuery({
    ...contractsQuery({
      cohortId: search.cohort,
      bootcampId: search.bootcamp,
      group: search.status,
      type: search.type,
      q: search.q,
    }),
    enabled: scoped || (!!access.data && pickableCohorts(cohorts).length === 0),
  });
  const [q, setQ] = useState(search.q ?? "");
  const debounced = useDebounced(q.trim());
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const counts = list.data?.pages[0]?.counts;
  const total = counts ? TYPES.reduce((n, t) => n + counts[t], 0) : undefined;
  const go = (next: ContractsSearch, replace = false) =>
    void navigate({ to: "/admin/administration/contracts", search: next, replace });
  // 저장한 계약을 같은 패널에서 연다. 저장을 마친 폼이 막지 않게 한다 (폼 상태는 다음 렌더에야 바뀐다)
  const openSaved = (id: string) =>
    void navigate({
      to: "/admin/administration/contracts",
      search: { ...search, contract: id },
      replace: true,
      ignoreBlocker: true,
    });

  // 과정·기수가 없으면 처음 범위로 (F96)
  useEffect(() => {
    if (scoped || !access.data) return;
    const scope = initialScope(access.data.cohorts);
    if (scope) void navigate({ to: "/admin/administration/contracts", search: { ...search, ...scope }, replace: true });
  }, [scoped, access.data, search, navigate]);

  // 검색어는 입력이 멈추면 주소에 반영한다
  useEffect(() => {
    if ((search.q ?? "") === debounced) return;
    void navigate({
      to: "/admin/administration/contracts",
      search: { ...search, q: debounced || undefined },
      replace: true,
    });
  }, [debounced, search, navigate]);

  const cohort = cohorts.find((c) => c.id === search.cohort);
  const filtered = !!(search.q || search.type || search.status);
  const [today] = useState(() => formatKst(new Date(), "yyyy-MM-dd"));

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        icon={FileSignature}
        title="계약"
        description="멘토·강사와 SW·장비 등 과정의 계약을 등록하고 진행 상태를 관리해요."
        actions={
          canManage ? (
            <Button onClick={() => go({ ...search, contract: "new" })}>
              <Plus aria-hidden />
              계약 추가
            </Button>
          ) : null
        }
      />
      <nav aria-label="계약 종류">
        <ul className="flex gap-1 border-b border-border">
          {[undefined, ...TYPES].map((t) => {
            const active = t === search.type;
            const count = counts ? (t ? counts[t] : total) : undefined;
            const label = t ? TYPE_LABELS[t] : "전체";
            return (
              <li key={label}>
                <Link
                  to="/admin/administration/contracts"
                  search={{ ...search, type: t, contract: undefined }}
                  aria-current={active ? "page" : undefined}
                  aria-label={count === undefined ? label : `${label} ${count}`}
                  className={cn(
                    "-mb-px inline-flex h-10 items-center gap-1.5 border-b-2 px-3 text-body outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    active
                      ? "border-primary text-body-strong text-primary-text"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  {label}
                  {count === undefined ? null : (
                    <span
                      className={cn(
                        "rounded-full px-1.5 text-caption-strong",
                        active ? "bg-sidebar-accent text-sidebar-accent-foreground" : "bg-muted text-muted-foreground",
                      )}
                    >
                      {count}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="flex items-center gap-2">
        <Select
          value={search.status ?? "open"}
          onValueChange={(v) => go({ ...search, status: v === "open" ? undefined : (v as StatusGroup) })}
        >
          <SelectTrigger aria-label="상태" className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(GROUP_LABELS) as StatusGroup[]).map((g) => (
              <SelectItem key={g} value={g}>
                {GROUP_LABELS[g]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="relative ml-auto w-70">
          <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="계약 검색"
            placeholder="명칭·이름·업체명 검색"
            value={q}
            maxLength={50}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>
      {list.isPending && list.fetchStatus !== "idle" ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : list.isError ? (
        <ErrorState onRetry={() => void list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={FileText}
          title={filtered ? "찾는 계약이 없어요" : "등록한 계약이 없어요"}
          description={canManage && !filtered ? "[계약 추가]로 이 과정·기수의 계약을 등록해요." : undefined}
        />
      ) : (
        <div
          role="table"
          aria-label="계약"
          className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm"
        >
          <div
            role="row"
            className={cn(COLUMNS, "bg-muted/70 px-5 py-3 text-caption-strong tracking-wide text-muted-foreground")}
          >
            {["계약 명칭", "종류", "이름 또는 업체명", "과정 / 기수", "기간", "금액", "상태", "담당"].map((h) => (
              <span key={h} role="columnheader" className={h === "금액" ? "text-right" : undefined}>
                {h}
              </span>
            ))}
          </div>
          {items.map((c) => (
            <ContractRow key={c.id} contract={c} search={search} selected={c.id === search.contract} today={today} />
          ))}
        </div>
      )}
      {list.hasNextPage ? (
        <LoadMore
          loading={list.isFetchingNextPage}
          label="다음 계약을 불러오는 중…"
          onVisible={() => void list.fetchNextPage()}
        />
      ) : null}
      {search.contract ? (
        <ContractSheet
          key={search.contract}
          contractId={search.contract}
          canManage={canManage}
          scope={{ cohortId: search.cohort, bootcampId: search.bootcamp ?? cohort?.bootcamp_id }}
          onOpen={openSaved}
          onClose={() => go({ ...search, contract: undefined })}
        />
      ) : null}
    </div>
  );
}

/** 이름 또는 업체명 아랫줄: 멘토 닉네임·가입 전, 업체 담당자, 그 밖은 비움 */
function partySub(c: Contract): string {
  if (c.contract_type === "MENTOR") {
    const p = c.linked_profile;
    if (!p) return "";
    return p.display_name && p.display_name !== p.name ? p.display_name : "";
  }
  return c.contact_person_name ? `담당 ${c.contact_person_name}` : "";
}

function ContractRow({
  contract: c,
  search,
  selected,
  today,
}: {
  contract: Contract;
  search: ContractsSearch;
  selected: boolean;
  today: string;
}) {
  const status = STATUS[c.status];
  const closed = c.status === "ENDED" || c.status === "CANCELED" || c.status === "TERMINATED";
  const sub = partySub(c);
  const hint = periodHint(c, today);
  return (
    <div
      role="row"
      aria-label={c.title}
      className={cn(
        COLUMNS,
        "group relative border-t border-border px-5 py-3.5 transition-colors hover:bg-sidebar-accent/40",
        selected && "bg-sidebar-accent/60",
        closed && "opacity-70",
      )}
    >
      {selected ? <span aria-hidden className="absolute inset-y-2 left-0 w-1 rounded-r-full bg-primary" /> : null}
      <span role="cell" className="flex min-w-0 flex-col">
        <Link
          to="/admin/administration/contracts"
          search={{ ...search, contract: c.id }}
          className="truncate text-body-strong text-foreground group-hover:text-primary-text after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring"
        >
          {c.title}
        </Link>
        {c.contract_file ? null : <span className="text-caption text-muted-foreground">계약서 없음</span>}
      </span>
      <span role="cell">
        <ContractTypeBadge type={c.contract_type} />
      </span>
      <span role="cell" className="flex min-w-0 flex-col">
        <span className="truncate text-body text-foreground">{c.contractor_name}</span>
        {sub ? <span className="truncate text-caption text-muted-foreground">{sub}</span> : null}
      </span>
      <span role="cell" className="truncate text-body text-foreground" title={academyText(c)}>
        {academyText(c)}
      </span>
      <span role="cell" className="flex flex-col">
        <span className="text-body text-foreground tabular-nums">{period(c)}</span>
        {hint ? (
          <span className={cn("text-caption", hint.soon ? "text-primary-text" : "text-muted-foreground")}>
            {hint.text}
          </span>
        ) : null}
      </span>
      <span role="cell" className="flex min-w-0 flex-col items-end text-right">
        <span className="truncate text-body-strong text-foreground tabular-nums">{amountText(c)}</span>
        <span className="truncate text-caption text-muted-foreground">{amountSub(c)}</span>
      </span>
      <span role="cell">
        <Badge variant={status.badge}>{status.label}</Badge>
      </span>
      <span role="cell" className="truncate text-body text-foreground">
        {c.manager_name ?? "—"}
      </span>
    </div>
  );
}
