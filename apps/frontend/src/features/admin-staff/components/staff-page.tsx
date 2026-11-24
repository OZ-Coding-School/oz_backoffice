import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { Plus, Search, Users } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LoadMore } from "@/components/load-more";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { EMPLOYMENT_TYPE_LABELS, STAFF_ROLE_LABELS } from "@/features/auth/messages";
import { staffOptionsQuery, teamsOf, type StaffOptions } from "@/features/auth/staff-api";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { formatKst } from "@/lib/datetime";
import { useDebounced } from "@/lib/use-debounced";
import { cn } from "@/lib/utils";

import {
  assignmentsSummary,
  employeesQuery,
  staffMembersQuery,
  type Employee,
  type EmployeeFilter,
  type StaffMember,
  type StaffTarget,
} from "../api";
import { AddStaffDialog, EditEmployeeDialog, RemoveStaffDialog } from "./staff-dialogs";

export type StaffTab = "employees" | "staff";

export interface StaffSearch {
  tab?: "staff";
  q?: string;
  department?: string;
  team?: string;
  bootcamp?: string;
  cohort?: string;
}

const ALL = "all";

/** 직원·담당자 (Figma `직원·담당자 (FE-15c)`, F62·A83). 권한이 있는 탭만 보인다. 데스크톱만(F58) */
export function StaffPage({ search }: { search: StaffSearch }) {
  const access = useQuery(staffAccessQuery);
  const options = useQuery(staffOptionsQuery);
  const canManageOrg = access.data ? hasPermission(access.data, "org.manage") : false;
  const canAssign = access.data ? hasPermission(access.data, "staff.assign") : false;
  const tab: StaffTab = search.tab === "staff" && canAssign ? "staff" : "employees";
  const tabs: { value: StaffTab; label: string; show: boolean }[] = [
    { value: "employees", label: "직원", show: canManageOrg || canAssign },
    { value: "staff", label: "담당자", show: canAssign },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">직원·담당자</h1>
        <p className="text-body text-muted-foreground">직원의 소속을 관리하고 과정·기수 담당자를 배정해요.</p>
      </div>
      <nav aria-label="직원·담당자 구분">
        <ul className="flex gap-1 border-b border-border">
          {tabs
            .filter((t) => t.show)
            .map((t) => {
              const active = t.value === tab;
              return (
                <li key={t.value}>
                  <Link
                    to="/admin/members/staff"
                    search={t.value === "staff" ? { tab: "staff" } : {}}
                    activeOptions={{ exact: true, includeSearch: true }}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "-mb-px inline-flex h-10 items-center border-b-2 px-3 text-body outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      active
                        ? "border-primary text-primary-text"
                        : "border-transparent text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {t.label}
                  </Link>
                </li>
              );
            })}
        </ul>
      </nav>
      {!options.data || !access.data ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : tab === "staff" ? (
        <StaffTabView search={search} options={options.data} />
      ) : (
        <EmployeesTab search={search} options={options.data} canEdit={canManageOrg} />
      )}
    </div>
  );
}

function FilterSelect({
  label,
  value,
  allLabel,
  items,
  onChange,
  className,
}: {
  label: string;
  value: string | undefined;
  allLabel: string;
  items: { value: string; label: string }[];
  onChange: (v: string | undefined) => void;
  className?: string;
}) {
  return (
    <Select value={value ?? ALL} onValueChange={(v) => onChange(v === ALL ? undefined : v)}>
      <SelectTrigger aria-label={label} className={cn("w-48", className)}>
        <SelectValue placeholder={allLabel} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{allLabel}</SelectItem>
        {items.map((i) => (
          <SelectItem key={i.value} value={i.value}>
            {i.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function EmployeesTab({ search, options, canEdit }: { search: StaffSearch; options: StaffOptions; canEdit: boolean }) {
  const navigate = useNavigate();
  const filter: EmployeeFilter = { q: search.q, departmentId: search.department, teamId: search.team };
  const list = useInfiniteQuery(employeesQuery(filter));
  const [q, setQ] = useState(search.q ?? "");
  const debounced = useDebounced(q.trim());
  const [editing, setEditing] = useState<Employee | null>(null);
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];

  // 검색어는 입력이 멈추면 주소에 반영한다
  useEffect(() => {
    if ((search.q ?? "") === debounced) return;
    void navigate({
      to: "/admin/members/staff",
      search: { ...search, q: debounced || undefined },
      replace: true,
    });
  }, [debounced, search, navigate]);

  const setFilter = (next: Partial<StaffSearch>) =>
    void navigate({ to: "/admin/members/staff", search: { ...search, ...next } });

  return (
    <>
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="직원 검색"
            placeholder="이름·이메일 검색"
            value={q}
            maxLength={50}
            onChange={(e) => setQ(e.target.value)}
            className="max-w-80 pl-9"
          />
        </div>
        <FilterSelect
          label="부서"
          value={search.department}
          allLabel="전체 부서"
          items={options.departments.map((d) => ({ value: d.id, label: d.name }))}
          onChange={(department) => setFilter({ department, team: undefined })}
        />
        <FilterSelect
          label="팀"
          value={search.team}
          allLabel="전체 팀"
          items={(search.department ? teamsOf(options, search.department) : options.teams).map((t) => ({
            value: t.id,
            label: t.name,
          }))}
          onChange={(team) => setFilter({ team })}
        />
      </div>
      {list.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : list.isError ? (
        <ErrorState onRetry={() => void list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState icon={Users} title={search.q ? "찾는 직원이 없어요" : "직원이 없어요"} />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <table className="w-full text-left text-body">
            <thead className="bg-muted text-caption text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  이름
                </th>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  이메일
                </th>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  부서 · 팀
                </th>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  직위
                </th>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  고용 형태
                </th>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  담당
                </th>
                {canEdit ? (
                  <th scope="col" className="w-24 px-4 py-2.5">
                    <span className="sr-only">동작</span>
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id} className="border-t border-border">
                  <td className="px-4 py-3 text-body-strong text-foreground">{e.user?.name ?? "—"}</td>
                  <td className="px-4 py-3 break-all text-foreground">{e.user?.email ?? "—"}</td>
                  <td className="px-4 py-3 text-foreground">
                    {options.departments.find((d) => d.id === e.department_id)?.name ?? "—"} ·{" "}
                    {e.team_id ? (options.teams.find((t) => t.id === e.team_id)?.name ?? "—") : "부서 직속"}
                  </td>
                  <td className="px-4 py-3 text-foreground">
                    {options.positions.find((p) => p.id === e.position_id)?.name ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-foreground">
                    {EMPLOYMENT_TYPE_LABELS[e.employment_type] ?? e.employment_type}
                  </td>
                  <td className="px-4 py-3 text-foreground">{assignmentsSummary(e.assignments ?? [])}</td>
                  {canEdit ? (
                    <td className="px-4 py-3">
                      <div className="flex justify-end">
                        <Button
                          size="sm"
                          variant="outline"
                          aria-label={`${e.user?.name ?? "직원"} 수정`}
                          onClick={() => setEditing(e)}
                        >
                          수정
                        </Button>
                      </div>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {list.hasNextPage ? (
        <LoadMore
          loading={list.isFetchingNextPage}
          label="다음 직원을 불러오는 중…"
          onVisible={() => void list.fetchNextPage()}
        />
      ) : null}
      {editing ? <EditEmployeeDialog employee={editing} options={options} onClose={() => setEditing(null)} /> : null}
    </>
  );
}

function StaffTabView({ search, options }: { search: StaffSearch; options: StaffOptions }) {
  const navigate = useNavigate();
  const access = useQuery(staffAccessQuery);
  const bootcamps = [...options.bootcamps].sort((a, b) => a.name.localeCompare(b.name, "ko"));
  const bootcampId = search.bootcamp;
  const cohorts = (access.data?.cohorts ?? [])
    .filter((c) => c.bootcamp_id === bootcampId)
    .sort((a, b) => b.cohort_number - a.cohort_number);
  const bootcampName = bootcamps.find((b) => b.id === bootcampId)?.name ?? "";
  const cohort = cohorts.find((c) => c.id === search.cohort);
  const target: StaffTarget | null = cohort
    ? { kind: "cohort", id: cohort.id }
    : bootcampId
      ? { kind: "bootcamp", id: bootcampId }
      : null;
  const targetName = cohort ? `${bootcampName} ${cohort.cohort_number}기` : bootcampName;
  const members = useQuery({ ...staffMembersQuery(target ?? { kind: "bootcamp", id: "" }), enabled: !!target });
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<StaffMember | null>(null);

  const setTarget = (next: Partial<StaffSearch>) =>
    void navigate({ to: "/admin/members/staff", search: { ...search, tab: "staff" as const, ...next } });

  return (
    <>
      <div className="flex items-center gap-2">
        <FilterSelect
          label="과정"
          value={bootcampId}
          allLabel="과정을 고르세요"
          items={bootcamps.map((b) => ({ value: b.id, label: b.name }))}
          onChange={(bootcamp) => setTarget({ bootcamp, cohort: undefined })}
          className="w-60"
        />
        {bootcampId ? (
          <FilterSelect
            label="기수"
            value={search.cohort}
            allLabel="과정 전체"
            items={cohorts.map((c) => ({ value: c.id, label: `${c.cohort_number}기` }))}
            onChange={(c) => setTarget({ cohort: c })}
          />
        ) : null}
        <div className="flex-1" />
        {target ? (
          <Button onClick={() => setAdding(true)}>
            <Plus aria-hidden />
            담당자 추가
          </Button>
        ) : null}
      </div>
      {!target ? (
        <EmptyState
          icon={Users}
          title="과정을 고르세요"
          description="과정 담당자를 보거나, 기수까지 골라 기수 담당자를 봐요."
        />
      ) : members.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : members.isError ? (
        <ErrorState onRetry={() => void members.refetch()} />
      ) : (members.data ?? []).length === 0 ? (
        <EmptyState icon={Users} title={`${targetName} 담당자가 없어요`} />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <table aria-label={`${targetName} 담당자`} className="w-full text-left text-body">
            <thead className="bg-muted text-caption text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  이름
                </th>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  이메일
                </th>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  역할
                </th>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  배정일
                </th>
                <th scope="col" className="w-24 px-4 py-2.5">
                  <span className="sr-only">동작</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {(members.data ?? []).map((m) => (
                <tr key={m.id} className="border-t border-border">
                  <td className="px-4 py-3 text-body-strong text-foreground">{m.user?.name ?? "—"}</td>
                  <td className="px-4 py-3 break-all text-foreground">{m.user?.email ?? "—"}</td>
                  <td className="px-4 py-3 text-foreground">{STAFF_ROLE_LABELS[m.role]}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {m.created_at ? formatKst(m.created_at, "yyyy.MM.dd") : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end">
                      <Button
                        size="sm"
                        variant="outline"
                        aria-label={`${m.user?.name ?? "담당자"} 해제`}
                        onClick={() => setRemoving(m)}
                      >
                        해제
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {adding && target ? (
        <AddStaffDialog
          target={target}
          targetName={targetName}
          members={members.data ?? []}
          options={options}
          onClose={() => setAdding(false)}
        />
      ) : null}
      {removing && target ? (
        <RemoveStaffDialog
          target={target}
          targetName={targetName}
          member={removing}
          onClose={() => setRemoving(null)}
        />
      ) : null}
    </>
  );
}
