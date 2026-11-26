import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronDown, ChevronRight, Search, Users } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { EMPLOYMENT_TYPE_LABELS } from "@/features/auth/messages";
import { staffOptionsQuery, type StaffOptions } from "@/features/auth/staff-api";
import { staffAccessQuery } from "@/features/staff/api";
import { cn } from "@/lib/utils";

import { assignmentsSummary, employeesQuery, type Employee } from "../api";
import { groupEmployees } from "../groups";
import { EmployeeSheet } from "./employee-sheet";

const COLUMNS = "grid grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_88px_minmax(0,1.4fr)] items-center gap-3";

/** 조직 설정 > 직원 (F67): 부서 › 팀 묶음 목록 + 오른쪽 슬라이드 패널 */
export function EmployeesPage({ employeeId }: { employeeId?: string }) {
  const employees = useQuery(employeesQuery);
  const options = useQuery(staffOptionsQuery);
  const access = useQuery(staffAccessQuery);
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const groups = useMemo(
    () => (employees.data && options.data ? groupEmployees(employees.data, options.data, q) : []),
    [employees.data, options.data, q],
  );
  const selected = employees.data?.find((e) => e.id === employeeId);
  const searching = q.trim() !== "";

  const toggle = (id: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">직원</h1>
        <p className="text-body text-muted-foreground">부서·팀별로 직원을 보고, 소속·직위·담당을 바꿔요.</p>
      </div>
      {employees.isPending || options.isPending || access.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : employees.isError || options.isError || access.isError ? (
        <ErrorState onRetry={() => void Promise.all([employees.refetch(), options.refetch(), access.refetch()])} />
      ) : (
        <section aria-label="직원 목록" className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
          <div className="flex items-center gap-3 border-b border-border px-4 py-3">
            <div className="relative w-70">
              <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                aria-label="직원 검색"
                placeholder="이름·이메일 검색"
                value={q}
                maxLength={50}
                onChange={(e) => setQ(e.target.value)}
                className="pl-9"
              />
            </div>
            <span className="text-label text-muted-foreground">직원 {groups.reduce((n, d) => n + d.count, 0)}명</span>
            <div className="ml-auto flex gap-1">
              <Button variant="ghost" size="sm" onClick={() => setCollapsed(new Set())}>
                모두 펼치기
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setCollapsed(new Set(groups.map((d) => d.id)))}>
                모두 접기
              </Button>
            </div>
          </div>
          {groups.length === 0 ? (
            <EmptyState
              icon={Users}
              title={searching ? "찾는 직원이 없어요" : "직원이 없어요"}
              {...(searching ? { description: "이름이나 이메일을 다시 확인해 주세요." } : {})}
              className="m-4"
            />
          ) : (
            <div role="table" aria-label="직원">
              <div
                role="row"
                className={cn(
                  COLUMNS,
                  "border-b border-border bg-muted py-2 pr-4 pl-10 text-caption text-muted-foreground",
                )}
              >
                <span role="columnheader">이름·이메일</span>
                <span role="columnheader">직위</span>
                <span role="columnheader">고용 형태</span>
                <span role="columnheader">담당</span>
              </div>
              {groups.map((d) => {
                // 검색 중에는 맞는 직원이 보이도록 모두 펼친다
                const open = searching || !collapsed.has(d.id);
                return (
                  <div key={d.id} role="rowgroup" aria-label={d.name}>
                    <div role="row" className="border-b border-border bg-muted">
                      <div role="cell">
                        <button
                          type="button"
                          aria-expanded={open}
                          onClick={() => toggle(d.id)}
                          className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                        >
                          {open ? (
                            <ChevronDown aria-hidden className="size-4" />
                          ) : (
                            <ChevronRight aria-hidden className="size-4" />
                          )}
                          <span className="text-body-strong text-foreground">{d.name}</span>
                          <span className="text-caption text-muted-foreground">{d.count}명</span>
                        </button>
                      </div>
                    </div>
                    {open
                      ? d.teams.map((t) => (
                          <div key={t.id ?? "none"} role="rowgroup" aria-label={`${d.name} ${t.name}`}>
                            <div role="row" className="flex gap-1.5 pt-2.5 pb-1 pl-10 text-caption">
                              <span role="cell" className="font-bold text-muted-foreground">
                                {t.name}
                              </span>
                              <span role="cell" className="text-muted-foreground">
                                {t.employees.length}명
                              </span>
                            </div>
                            {t.employees.map((e) => (
                              <EmployeeRow
                                key={e.id}
                                employee={e}
                                options={options.data}
                                selected={e.id === employeeId}
                              />
                            ))}
                          </div>
                        ))
                      : null}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}
      {selected && options.data && access.data ? (
        <EmployeeSheet
          key={selected.id}
          employee={selected}
          options={options.data}
          access={access.data}
          onClose={() => void navigate({ to: "/admin/org/employees", search: {} })}
        />
      ) : null}
    </div>
  );
}

function EmployeeRow({
  employee: e,
  options,
  selected,
}: {
  employee: Employee;
  options: StaffOptions;
  selected: boolean;
}) {
  const name = e.user?.name ?? "—";
  return (
    <div
      role="row"
      aria-label={name}
      className={cn(COLUMNS, "relative border-b border-border py-2.5 pr-4 pl-10 last:border-b-0 hover:bg-accent/60", {
        "bg-accent": selected,
      })}
    >
      <div role="cell" className="flex min-w-0 flex-col">
        <span className="flex items-center gap-1.5">
          {/* 행 전체를 누를 수 있게 링크를 행 크기로 늘린다 */}
          <Link
            to="/admin/org/employees"
            search={{ employee: e.id }}
            className={cn(
              "truncate text-body-strong text-foreground after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring",
              { "text-primary": selected },
            )}
          >
            {name}
          </Link>
          {e.is_super_admin ? <Badge variant="primary">최고 관리자</Badge> : null}
        </span>
        <span className="truncate text-caption text-muted-foreground">{e.user?.email ?? "—"}</span>
      </div>
      <span role="cell" className="truncate text-body text-foreground">
        {options.positions.find((p) => p.id === e.position_id)?.name ?? "—"}
      </span>
      <span role="cell" className="text-body text-foreground">
        {EMPLOYMENT_TYPE_LABELS[e.employment_type] ?? e.employment_type}
      </span>
      <span
        role="cell"
        className={cn("truncate text-body", e.assignments?.length ? "text-foreground" : "text-muted-foreground")}
      >
        {assignmentsSummary(e.assignments ?? [])}
      </span>
    </div>
  );
}
