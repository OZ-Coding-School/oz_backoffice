import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { Building2, ChevronDown, ChevronRight, Network } from "lucide-react";
import { useState, type ReactNode } from "react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { staffOptionsQuery, type StaffOptions } from "@/features/auth/staff-api";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { cn } from "@/lib/utils";

import { departmentsQuery, teamsQuery, type Department, type Team } from "../api";
import { DepartmentSheet } from "./department-sheet";
import { TeamSheet } from "./team-sheet";

export interface DepartmentsSearch {
  view?: "tree";
  department?: string;
  team?: string;
}

const COLUMNS = "grid grid-cols-[minmax(0,1.2fr)_minmax(0,1.6fr)_minmax(0,1.8fr)_72px] items-center gap-3";
const COMPANY = "넥스트러너스";

const byName = <T extends { name: string }>(a: T, b: T) => a.name.localeCompare(b.name, "ko");

/** 조직 설정 > 부서 (F69): 목록·조직도 두 보기 + 오른쪽 슬라이드 패널 */
export function DepartmentsPage({ search }: { search: DepartmentsSearch }) {
  const departments = useQuery(departmentsQuery);
  const teams = useQuery(teamsQuery);
  const options = useQuery(staffOptionsQuery);
  const access = useQuery(staffAccessQuery);
  const navigate = useNavigate();
  const [creating, setCreating] = useState<"department" | "team" | null>(null);
  const tree = search.view === "tree";
  const viewSearch = tree ? { view: "tree" as const } : {};
  const close = () => {
    setCreating(null);
    void navigate({ to: "/admin/org/departments", search: viewSearch });
  };

  if (departments.isPending || teams.isPending || options.isPending || access.isPending)
    return (
      <Frame>
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      </Frame>
    );
  if (departments.isError || teams.isError || options.isError || access.isError)
    return (
      <Frame>
        <ErrorState
          onRetry={() =>
            void Promise.all([departments.refetch(), teams.refetch(), options.refetch(), access.refetch()])
          }
        />
      </Frame>
    );

  const canManage = hasPermission(access.data, "org.department.manage");
  const allDepartments = [...departments.data].sort(byName);
  const allTeams = [...teams.data].sort(byName);
  const teamsOf = (d: Department) => allTeams.filter((t) => t.department_id === d.id);
  const employees = allDepartments.reduce((n, d) => n + d.employee_count, 0);
  const department = allDepartments.find((d) => d.id === search.department);
  const team = allTeams.find((t) => t.id === search.team);

  return (
    <Frame>
      <section aria-label="부서 목록" className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
        <div className="flex items-center gap-3 border-b border-border px-4 py-3">
          <nav aria-label="보기" className="flex gap-0.5 rounded-lg bg-muted p-1">
            {(
              [
                ["목록", {}],
                ["트리", { view: "tree" as const }],
              ] as const
            ).map(([label, s]) => {
              const active = (label === "트리") === tree;
              return (
                <Link
                  key={label}
                  to="/admin/org/departments"
                  search={s}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "rounded-md px-3.5 py-1.5 text-label focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                    active
                      ? "bg-card font-bold text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
          <span className="text-label text-muted-foreground">
            부서 {allDepartments.length}개 · 팀 {allTeams.length}개 · 직원 {employees}명
          </span>
          {canManage ? (
            <div className="ml-auto flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setCreating("team")} disabled={!allDepartments.length}>
                팀 추가
              </Button>
              <Button size="sm" onClick={() => setCreating("department")}>
                부서 추가
              </Button>
            </div>
          ) : null}
        </div>
        {allDepartments.length === 0 ? (
          <EmptyState
            icon={Building2}
            title="부서가 없어요"
            {...(canManage ? { description: "[부서 추가]로 첫 부서를 만들어 주세요." } : {})}
            className="m-4"
          />
        ) : tree ? (
          <OrgChart departments={allDepartments} teamsOf={teamsOf} search={search} employees={employees} />
        ) : (
          <ListView departments={allDepartments} teamsOf={teamsOf} options={options.data} search={search} />
        )}
      </section>
      {creating === "department" || department ? (
        <DepartmentSheet
          key={department?.id ?? "new"}
          department={creating === "department" ? null : (department ?? null)}
          teams={department ? teamsOf(department) : []}
          canManage={canManage}
          onClose={close}
        />
      ) : null}
      {creating === "team" || team ? (
        <TeamSheet
          key={team?.id ?? "new"}
          team={creating === "team" ? null : (team ?? null)}
          departments={allDepartments}
          teams={allTeams}
          bootcamps={options.data.bootcamps}
          canManage={canManage}
          onClose={close}
        />
      ) : null}
    </Frame>
  );
}

function Frame({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader icon={Network} title="부서" description="부서와 팀을 만들고, 팀이 담당하는 과정을 정해요." />
      {children}
    </div>
  );
}

function bootcampNames(options: StaffOptions, team: Team): string {
  return (
    team.bootcamp_ids
      .map((id) => options.bootcamps.find((b) => b.id === id)?.name)
      .filter(Boolean)
      .join(", ") || "—"
  );
}

function ListView({
  departments,
  teamsOf,
  options,
  search,
}: {
  departments: Department[];
  teamsOf: (d: Department) => Team[];
  options: StaffOptions;
  search: DepartmentsSearch;
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const toggle = (id: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  return (
    <div role="table" aria-label="부서">
      <div
        role="row"
        className={cn(COLUMNS, "border-b border-border bg-muted px-4 py-2 text-caption text-muted-foreground")}
      >
        <span role="columnheader">이름</span>
        <span role="columnheader">설명</span>
        <span role="columnheader">담당 과정</span>
        <span role="columnheader" className="text-right">
          직원
        </span>
      </div>
      {departments.map((d) => {
        const teams = teamsOf(d);
        const open = !collapsed.has(d.id);
        const courses = teams.reduce((n, t) => n + t.bootcamp_ids.length, 0);
        return (
          <div key={d.id} role="rowgroup" aria-label={d.name}>
            <div
              role="row"
              aria-label={d.name}
              className={cn(COLUMNS, "relative border-b border-border bg-muted px-4 py-2.5 hover:bg-accent/60", {
                "bg-accent": search.department === d.id,
              })}
            >
              <span role="cell" className="flex min-w-0 items-center gap-1.5">
                <button
                  type="button"
                  aria-expanded={open}
                  aria-label={`${d.name} 팀 ${open ? "접기" : "펼치기"}`}
                  onClick={() => toggle(d.id)}
                  className="relative z-10 -ml-1 inline-flex size-6 items-center justify-center rounded-md hover:bg-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  {open ? (
                    <ChevronDown aria-hidden className="size-4" />
                  ) : (
                    <ChevronRight aria-hidden className="size-4" />
                  )}
                </button>
                <Link
                  to="/admin/org/departments"
                  search={{ department: d.id }}
                  className="truncate text-body-strong text-foreground after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring"
                >
                  {d.name}
                </Link>
              </span>
              <span role="cell" className="truncate text-body text-muted-foreground">
                {d.description}
              </span>
              <span role="cell" className="truncate text-body text-foreground">
                {teams.length ? `팀 ${teams.length}개 · 과정 ${courses}개` : "—"}
              </span>
              <span role="cell" className="text-right text-body-strong text-foreground">
                {d.employee_count}명
              </span>
            </div>
            {open
              ? teams.map((t) => (
                  <div
                    key={t.id}
                    role="row"
                    aria-label={t.name}
                    className={cn(COLUMNS, "relative border-b border-border px-4 py-2.5 hover:bg-accent/60", {
                      "bg-accent": search.team === t.id,
                    })}
                  >
                    <span role="cell" className="min-w-0 pl-7">
                      <Link
                        to="/admin/org/departments"
                        search={{ team: t.id }}
                        className={cn(
                          "truncate text-body-strong text-foreground after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring",
                          { "text-primary": search.team === t.id },
                        )}
                      >
                        {t.name}
                      </Link>
                    </span>
                    <span role="cell" className="truncate text-body text-muted-foreground">
                      {t.description || "—"}
                    </span>
                    <span role="cell" className="truncate text-body text-foreground">
                      {bootcampNames(options, t)}
                    </span>
                    <span role="cell" className="text-right text-body-strong text-foreground">
                      {t.employee_count}명
                    </span>
                  </div>
                ))
              : null}
          </div>
        );
      })}
    </div>
  );
}

/** 조직도: 회사 → 부서 → 팀 (F69) */
function OrgChart({
  departments,
  teamsOf,
  search,
  employees,
}: {
  departments: Department[];
  teamsOf: (d: Department) => Team[];
  search: DepartmentsSearch;
  employees: number;
}) {
  const last = departments.length - 1;
  return (
    <section aria-label="조직도" className="overflow-x-auto px-8 py-10">
      <div className="mx-auto flex w-max flex-col items-center">
        <div className="rounded-lg bg-primary px-6 py-2.5 text-center text-primary-foreground">
          <p className="text-body-strong">{COMPANY}</p>
          <p className="text-caption">직원 {employees}명</p>
        </div>
        <div aria-hidden className="h-6 w-px bg-border" />
        <div className="flex">
          {departments.map((d, i) => {
            const teams = teamsOf(d);
            return (
              <div key={d.id} className="relative flex flex-col items-center px-4">
                {departments.length > 1 ? (
                  <span
                    aria-hidden
                    className={cn("absolute top-0 h-px bg-border", {
                      "right-0 left-1/2": i === 0,
                      "right-1/2 left-0": i === last,
                      "inset-x-0": i > 0 && i < last,
                    })}
                  />
                ) : null}
                <div aria-hidden className="h-5 w-px bg-border" />
                <ChartNode
                  title={d.name}
                  sub={`직원 ${d.employee_count}명 · 팀 ${teams.length}개`}
                  search={{ view: "tree", department: d.id }}
                  selected={search.department === d.id}
                />
                {teams.length ? (
                  <>
                    <div aria-hidden className="h-5 w-px bg-border" />
                    <div className="flex flex-col gap-3">
                      {teams.map((t) => (
                        <ChartNode
                          key={t.id}
                          title={t.name}
                          sub={`직원 ${t.employee_count}명 · 과정 ${t.bootcamp_ids.length}개`}
                          search={{ view: "tree", team: t.id }}
                          selected={search.team === t.id}
                          small
                        />
                      ))}
                    </div>
                  </>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function ChartNode({
  title,
  sub,
  search,
  selected,
  small = false,
}: {
  title: string;
  sub: string;
  search: DepartmentsSearch;
  selected: boolean;
  small?: boolean;
}) {
  return (
    <Link
      to="/admin/org/departments"
      search={search}
      aria-label={title}
      className={cn(
        "flex flex-col items-center rounded-lg border px-4 py-2.5 text-center transition-colors hover:border-primary focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
        small ? "w-42" : "w-46",
        selected ? "border-primary bg-accent" : "border-border bg-card",
      )}
    >
      <span className={cn("text-body-strong", selected ? "text-primary" : "text-foreground")}>{title}</span>
      <span className="text-caption text-muted-foreground">{sub}</span>
    </Link>
  );
}
