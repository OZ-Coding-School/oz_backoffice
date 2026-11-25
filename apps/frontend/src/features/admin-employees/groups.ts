import type { StaffOptions } from "@/features/auth/staff-api";

import type { Employee } from "./api";

export interface TeamGroup {
  /** 팀 id, 팀이 없으면 null ('팀 없음') */
  id: string | null;
  name: string;
  employees: Employee[];
}

export interface DepartmentGroup {
  id: string;
  name: string;
  count: number;
  teams: TeamGroup[];
}

export const NO_TEAM_LABEL = "팀 없음";

const byName = (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name, "ko");

/** 이름·이메일에 검색어가 들어간 직원 (대소문자 무시) */
export function matches(employee: Employee, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const user = employee.user;
  return !!user && (user.name.toLowerCase().includes(q) || user.email.toLowerCase().includes(q));
}

/**
 * 부서 › 팀으로 묶는다 (F67). 부서·팀·직원은 이름순, '팀 없음'은 부서의 맨 아래.
 * 검색어가 있으면 맞는 직원이 있는 묶음만 남긴다.
 */
export function groupEmployees(employees: readonly Employee[], options: StaffOptions, query = ""): DepartmentGroup[] {
  const departments = new Map<string, DepartmentGroup>();
  const teamName = (id: string) => options.teams.find((t) => t.id === id)?.name ?? "—";
  for (const employee of employees) {
    if (!matches(employee, query)) continue;
    let department = departments.get(employee.department_id);
    if (!department) {
      const name = options.departments.find((d) => d.id === employee.department_id)?.name ?? "—";
      department = { id: employee.department_id, name, count: 0, teams: [] };
      departments.set(employee.department_id, department);
    }
    let team = department.teams.find((t) => t.id === employee.team_id);
    if (!team) {
      team = {
        id: employee.team_id,
        name: employee.team_id ? teamName(employee.team_id) : NO_TEAM_LABEL,
        employees: [],
      };
      department.teams.push(team);
    }
    team.employees.push(employee);
    department.count += 1;
  }
  const userName = (e: Employee) => e.user?.name ?? "";
  return [...departments.values()].sort(byName).map((d) => ({
    ...d,
    teams: d.teams
      .sort((a, b) => (a.id === null ? 1 : b.id === null ? -1 : byName(a, b)))
      .map((t) => ({ ...t, employees: t.employees.sort((a, b) => userName(a).localeCompare(userName(b), "ko")) })),
  }));
}
