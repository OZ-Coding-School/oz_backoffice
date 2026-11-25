import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { FileText, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LoadMore } from "@/components/load-more";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { useDebounced } from "@/lib/use-debounced";
import { cn } from "@/lib/utils";

import { contractsQuery, type Contract, type ContractStatus, type EducatorType } from "../api";
import { linkedText, period, STATUS, TYPE_LABELS } from "../labels";
import { ContractSheet } from "./contract-sheet";

export interface ContractsSearch {
  status?: ContractStatus;
  type?: EducatorType;
  q?: string;
  /** 패널: 계약 id 또는 new */
  contract?: string;
}

const ALL = "all";
const COLUMNS = "grid grid-cols-[120px_56px_minmax(0,1fr)_196px_170px_96px_80px] items-center gap-4";

/** 행정 업무 > 계약 (F83): 상태·유형·검색 + 표, 행을 누르면 오른쪽 패널 */
export function ContractsPage({ search }: { search: ContractsSearch }) {
  const navigate = useNavigate();
  const access = useQuery(staffAccessQuery);
  const canManage = !!access.data && hasPermission(access.data, "educator.contract.manage");
  const list = useInfiniteQuery(contractsQuery({ status: search.status, type: search.type, q: search.q }));
  const [q, setQ] = useState(search.q ?? "");
  const debounced = useDebounced(q.trim());
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
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

  // 검색어는 입력이 멈추면 주소에 반영한다
  useEffect(() => {
    if ((search.q ?? "") === debounced) return;
    void navigate({
      to: "/admin/administration/contracts",
      search: { ...search, q: debounced || undefined },
      replace: true,
    });
  }, [debounced, search, navigate]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <div className="flex flex-1 flex-col gap-1">
          <h1 className="text-h1 text-foreground">계약</h1>
          <p className="text-body text-muted-foreground">멘토·강사 계약서를 등록하고 확정·해지해요.</p>
        </div>
        {canManage ? <Button onClick={() => go({ ...search, contract: "new" })}>계약 추가</Button> : null}
      </div>
      <div className="flex items-center gap-2">
        <Select
          value={search.status ?? ALL}
          onValueChange={(v) => go({ ...search, status: v === ALL ? undefined : (v as ContractStatus) })}
        >
          <SelectTrigger aria-label="상태" className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>모든 상태</SelectItem>
            {(Object.keys(STATUS) as ContractStatus[]).map((s) => (
              <SelectItem key={s} value={s}>
                {STATUS[s].label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={search.type ?? ALL}
          onValueChange={(v) => go({ ...search, type: v === ALL ? undefined : (v as EducatorType) })}
        >
          <SelectTrigger aria-label="유형" className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>모든 유형</SelectItem>
            <SelectItem value="MENTOR">멘토</SelectItem>
            <SelectItem value="INSTRUCTOR">강사</SelectItem>
          </SelectContent>
        </Select>
        <div className="relative ml-auto w-65">
          <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="계약 검색"
            placeholder="계약자 이름·제목·휴대폰 검색"
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
          icon={FileText}
          title={search.q || search.status || search.type ? "찾는 계약이 없어요" : "등록한 계약이 없어요"}
        />
      ) : (
        <div className="flex flex-col gap-3">
          <div role="table" aria-label="계약" className="overflow-hidden rounded-xl border border-border bg-card">
            <div role="row" className={cn(COLUMNS, "bg-muted px-4 py-2.5 text-caption text-muted-foreground")}>
              {["계약자", "유형", "제목", "기간", "연결", "담당", "상태"].map((h) => (
                <span key={h} role="columnheader">
                  {h}
                </span>
              ))}
            </div>
            {items.map((c) => (
              <ContractRow key={c.id} contract={c} search={search} selected={c.id === search.contract} />
            ))}
          </div>
          <p className="text-caption text-muted-foreground">
            멘토 계약은 항상 멘토에 속해요(가입 전이면 가입하면 연결돼요). 작성 중인 계약만 내용을 고칠 수 있어요.
          </p>
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
          onOpen={openSaved}
          onClose={() => go({ ...search, contract: undefined })}
        />
      ) : null}
    </div>
  );
}

function ContractRow({
  contract: c,
  search,
  selected,
}: {
  contract: Contract;
  search: ContractsSearch;
  selected: boolean;
}) {
  const linked = linkedText(c);
  const status = STATUS[c.status];
  return (
    <div
      role="row"
      aria-label={`${c.contractor_name} ${c.title}`}
      className={cn(COLUMNS, "relative border-t border-border px-4 py-3 hover:bg-accent/60", selected && "bg-accent")}
    >
      <span role="cell" className="truncate">
        <Link
          to="/admin/administration/contracts"
          search={{ ...search, contract: c.id }}
          className="text-body-strong text-foreground after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring"
        >
          {c.contractor_name}
        </Link>
      </span>
      <span role="cell" className="text-body text-foreground">
        {TYPE_LABELS[c.educator_type]}
      </span>
      <span role="cell" className="truncate text-body text-foreground">
        {c.title}
      </span>
      <span role="cell" className="text-body text-foreground">
        {period(c)}
      </span>
      <span
        role="cell"
        className={cn("truncate text-body", linked.muted ? "text-muted-foreground" : "text-foreground")}
      >
        {linked.text}
      </span>
      <span role="cell" className="truncate text-body text-foreground">
        {c.manager_name ?? "—"}
      </span>
      <span role="cell">
        <Badge variant={status.badge}>{status.label}</Badge>
      </span>
    </div>
  );
}
