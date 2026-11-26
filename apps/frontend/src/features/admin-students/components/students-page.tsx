import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronDown, ChevronRight, RefreshCw, Search, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { maskPhone } from "@/features/profile/mask";
import { staffAccessQuery, type StaffCohort } from "@/features/staff/api";
import { formatKst } from "@/lib/datetime";
import { useDebounced } from "@/lib/use-debounced";
import { cn } from "@/lib/utils";

import { rosterQuery, type EnrollmentStatus, type RosterStudent } from "../api";
import { groupStudents, matches, type StudentGroup, type StudentGroupBy } from "../filter";
import { ENROLLMENT, ENROLLMENT_ORDER } from "../labels";
import { syncRunsQuery } from "../sync-api";
import { SyncSheet } from "./sync-sheet";

export interface StudentsSearch {
  cohort?: string;
  status?: EnrollmentStatus;
  q?: string;
  group?: StudentGroupBy;
  sync?: boolean;
}

const NO_GROUP = "none";
const COLUMNS = "grid grid-cols-[140px_150px_minmax(0,1fr)_80px_96px] items-center gap-3";
const COHORT_STATUS: Record<string, string> = {
  PLANNED: "개강 전",
  ONGOING: "진행 중",
  ENDED: "종료",
  INACTIVE: "비활성",
  ARCHIVED: "보관",
};

/** 학사 > 수강생 (F76): 과정·기수 선택(필수)·검색·수강 상태 탭 + 명단 표 */
export function StudentsPage({ search }: { search: StudentsSearch }) {
  const navigate = useNavigate();
  const access = useQuery(staffAccessQuery);
  const cohorts = useMemo(() => (access.data?.cohorts ?? []).filter((c) => c.status !== "ARCHIVED"), [access.data]);
  // 기수를 고르지 않았으면 담당 기수 중 첫 기수 (진행 중 먼저, A81 순서)
  const cohort = cohorts.find((c) => c.id === search.cohort) ?? cohorts[0];
  const go = (next: StudentsSearch) => void navigate({ to: "/admin/academy/students", search: next });

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        icon={Users}
        title="수강생"
        description="기수를 골라 Airtable 명단에서 동기화된 수강생을 봐요."
        actions={
          <>
            <LastSync />
            <Button variant="outline" size="sm" onClick={() => go({ ...search, sync: true })}>
              <RefreshCw aria-hidden />
              명단 동기화
            </Button>
          </>
        }
      />
      {access.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : !cohort ? (
        <EmptyState
          icon={Users}
          title="볼 수 있는 기수가 없어요"
          description="담당 기수가 생기면 여기서 수강생을 볼 수 있어요."
        />
      ) : (
        <CohortStudents
          key={cohort.id}
          cohorts={cohorts}
          cohort={cohort}
          search={search}
          onChange={(next) => go(next)}
        />
      )}
      {search.sync && access.data ? (
        <SyncSheet access={access.data} cohorts={cohorts} onClose={() => go({ ...search, sync: undefined })} />
      ) : null}
    </div>
  );
}

/** 마지막 동기화 시각 (보이는 실행 이력 중 가장 최근 성공) */
function LastSync() {
  const runs = useInfiniteQuery(syncRunsQuery);
  const last = runs.data?.pages[0]?.items.find((r) => r.status === "SUCCEEDED");
  if (!last) return null;
  return (
    <span className="pb-1 text-caption text-muted-foreground">
      마지막 동기화 {formatKst(last.finished_at ?? last.started_at, "M/d HH:mm")} · 매시간 자동
    </span>
  );
}

function CohortStudents({
  cohorts,
  cohort,
  search,
  onChange,
}: {
  cohorts: StaffCohort[];
  cohort: StaffCohort;
  search: StudentsSearch;
  onChange: (next: StudentsSearch) => void;
}) {
  const navigate = useNavigate();
  const roster = useQuery(rosterQuery(cohort.id));
  const [q, setQ] = useState(search.q ?? "");
  const debounced = useDebounced(q.trim());
  const bootcamps = useMemo(() => {
    const seen = new Map<string, string>();
    for (const c of cohorts) if (!seen.has(c.bootcamp_id)) seen.set(c.bootcamp_id, c.bootcamp_name);
    return [...seen.entries()].map(([id, name]) => ({ id, name }));
  }, [cohorts]);
  const sameBootcamp = cohorts
    .filter((c) => c.bootcamp_id === cohort.bootcamp_id)
    .sort((a, b) => b.cohort_number - a.cohort_number);

  // 검색어는 입력이 멈추면 주소에 반영한다
  useEffect(() => {
    if ((search.q ?? "") === debounced) return;
    void navigate({
      to: "/admin/academy/students",
      search: { ...search, q: debounced || undefined },
      replace: true,
    });
  }, [debounced, search, navigate]);

  const found = (roster.data ?? []).filter((s) => matches(s, search.q ?? ""));
  const counts = Object.fromEntries(
    ENROLLMENT_ORDER.map((st) => [st, found.filter((s) => s.status === st).length]),
  ) as Record<EnrollmentStatus, number>;
  const visible = search.status ? found.filter((s) => s.status === search.status) : found;
  const tabs: { value: EnrollmentStatus | undefined; label: string; count: number }[] = [
    { value: undefined, label: "전체", count: found.length },
    ...ENROLLMENT_ORDER.map((st) => ({ value: st, label: ENROLLMENT[st].label, count: counts[st] })),
  ];

  return (
    <>
      <div className="flex items-center gap-2">
        <Select
          value={cohort.bootcamp_id}
          onValueChange={(bootcampId) => {
            const first = cohorts.find((c) => c.bootcamp_id === bootcampId);
            if (first) onChange({ cohort: first.id, group: search.group });
          }}
        >
          <SelectTrigger aria-label="과정" className="w-60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {bootcamps.map((b) => (
              <SelectItem key={b.id} value={b.id}>
                {b.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={cohort.id} onValueChange={(id) => onChange({ cohort: id, group: search.group })}>
          <SelectTrigger aria-label="기수" className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {sameBootcamp.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.cohort_number}기 · {COHORT_STATUS[c.status] ?? c.status}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex-1" />
        <Select
          value={search.group ?? NO_GROUP}
          onValueChange={(v) =>
            onChange({ ...search, cohort: cohort.id, group: v === NO_GROUP ? undefined : (v as StudentGroupBy) })
          }
        >
          <SelectTrigger aria-label="묶어 보기" className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NO_GROUP}>묶지 않음</SelectItem>
            <SelectItem value="status">수강 상태별</SelectItem>
            <SelectItem value="signup">가입 상태별</SelectItem>
          </SelectContent>
        </Select>
        <div className="relative w-64">
          <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="수강생 검색"
            placeholder="이름·휴대폰·이메일 검색"
            value={q}
            maxLength={50}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>
      <nav aria-label="수강 상태">
        <ul className="flex gap-1 border-b border-border">
          {tabs.map((t) => {
            const active = t.value === search.status;
            return (
              <li key={t.label}>
                <Link
                  to="/admin/academy/students"
                  search={{
                    cohort: cohort.id,
                    ...(t.value ? { status: t.value } : {}),
                    q: search.q,
                    group: search.group,
                  }}
                  aria-current={active ? "page" : undefined}
                  aria-label={roster.data ? `${t.label} ${t.count}` : t.label}
                  className={cn(
                    "-mb-px inline-flex h-10 items-center gap-1.5 border-b-2 px-3 text-body outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    active
                      ? "border-primary text-primary-text"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t.label}
                  {roster.data ? <span>{t.count}</span> : null}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      {roster.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : roster.isError ? (
        <ErrorState onRetry={() => void roster.refetch()} />
      ) : visible.length === 0 ? (
        <EmptyState
          icon={Users}
          title={search.q || search.status ? "찾는 수강생이 없어요" : "수강생이 없어요"}
          {...(search.q ? { description: "이름·휴대폰·이메일을 다시 확인해 주세요." } : {})}
        />
      ) : (
        <div
          role="table"
          aria-label="수강생"
          className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm"
        >
          <div role="row" className={cn(COLUMNS, "bg-muted px-4 py-2.5 text-caption text-muted-foreground")}>
            {["이름", "휴대폰", "이메일", "가입", "수강 상태"].map((h) => (
              <span key={h} role="columnheader">
                {h}
              </span>
            ))}
          </div>
          {search.group
            ? groupStudents(visible, search.group).map((g) => (
                <GroupRows key={`${search.group}-${g.key}`} group={g} cohortId={cohort.id} />
              ))
            : visible.map((s) => <StudentRow key={s.id} student={s} cohortId={cohort.id} />)}
        </div>
      )}
      <p className="text-caption text-muted-foreground">
        휴대폰은 가려서 보여요. Airtable 원본에서 빠진 수강생은 보이지 않아요.
      </p>
    </>
  );
}

/** 접는 묶음 머리 + 건수 (F77), 처음엔 펼침 */
function GroupRows({ group, cohortId }: { group: StudentGroup; cohortId: string }) {
  const [open, setOpen] = useState(true);
  return (
    <div role="rowgroup" aria-label={`${group.label} ${group.items.length}명`}>
      <div role="row" className={cn("border-t border-border", group.tint)}>
        <span role="cell" className="block">
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="flex w-full items-center gap-2 px-4 py-2 text-left text-foreground outline-none hover:bg-foreground/5 focus-visible:ring-2 focus-visible:ring-ring"
          >
            {open ? <ChevronDown aria-hidden className="size-4" /> : <ChevronRight aria-hidden className="size-4" />}
            <Badge variant={group.badge}>{group.label}</Badge>
            <span className="text-caption text-muted-foreground">{group.items.length}명</span>
          </button>
        </span>
      </div>
      {open ? group.items.map((s) => <StudentRow key={s.id} student={s} cohortId={cohortId} />) : null}
    </div>
  );
}

function StudentRow({ student: s, cohortId }: { student: RosterStudent; cohortId: string }) {
  const status = ENROLLMENT[s.status];
  return (
    <div
      role="row"
      aria-label={s.name}
      className={cn(COLUMNS, "relative border-t border-border px-4 py-3 hover:bg-accent/60")}
    >
      <span role="cell" className="min-w-0">
        <Link
          to="/admin/academy/students/$studentId"
          params={{ studentId: s.id }}
          search={{ cohort: cohortId }}
          className="block truncate text-body-strong text-foreground after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring"
        >
          {s.name}
        </Link>
      </span>
      <span role="cell" className="text-body text-foreground">
        {maskPhone(s.phone_number) ?? "—"}
      </span>
      <span role="cell" className="truncate text-body text-muted-foreground">
        {s.email ?? "—"}
      </span>
      <span role="cell" className="text-body text-muted-foreground">
        {s.user_id ? "가입" : "미가입"}
      </span>
      <span role="cell">
        <Badge variant={status.badge}>{status.label}</Badge>
      </span>
    </div>
  );
}
