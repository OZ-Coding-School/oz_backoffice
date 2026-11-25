import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { staffKeys } from "@/features/auth/staff-api";

export type Department = components["schemas"]["DepartmentResponse"];
export type Team = components["schemas"]["app__contexts__organization__presentation__org_router__TeamResponse"];
export type OrgImpact = components["schemas"]["OrgImpactResponse"];
export type DepartmentBody = components["schemas"]["DepartmentCreateRequest"];
export type TeamBody = components["schemas"]["TeamCreateRequest"];

export const orgKeys = {
  all: ["admin-org"] as const,
  departments: () => ["admin-org", "departments"] as const,
  teams: () => ["admin-org", "teams"] as const,
  impact: (kind: ImpactKind, id: string) => ["admin-org", "impact", kind, id] as const,
};

export type ImpactKind = "department" | "team" | "position";

/** 부서 (이름순, 직원 수 A92) */
export const departmentsQuery = queryOptions({
  queryKey: orgKeys.departments(),
  queryFn: () => unwrap(api.GET("/api/v1/admin/departments")),
});

/** 팀과 담당 과정 (이름순, 직원 수 A92) */
export const teamsQuery = queryOptions({
  queryKey: orgKeys.teams(),
  queryFn: () => unwrap(api.GET("/api/v1/admin/teams")),
});

/** 지우거나 바꿀 때 영향받는 대상 (A93). 확인 창을 열 때만 읽고 늘 새로 읽는다 */
export function impactQuery(kind: ImpactKind, id: string) {
  return queryOptions({
    queryKey: orgKeys.impact(kind, id),
    staleTime: 0,
    queryFn: () => {
      if (kind === "department")
        return unwrap(
          api.GET("/api/v1/admin/departments/{department_id}/impact", { params: { path: { department_id: id } } }),
        );
      if (kind === "team")
        return unwrap(api.GET("/api/v1/admin/teams/{team_id}/impact", { params: { path: { team_id: id } } }));
      return unwrap(api.GET("/api/v1/admin/positions/{position_id}/impact", { params: { path: { position_id: id } } }));
    },
  });
}

/** 영향받는 대상이 하나라도 있는가 */
export function hasImpact(impact: OrgImpact): boolean {
  return (
    impact.employees.length +
      impact.registrations.length +
      (impact.teams?.length ?? 0) +
      (impact.bootcamps?.length ?? 0) >
    0
  );
}

function useInvalidate() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: orgKeys.all }),
      // 부서·팀 이름은 직원·가입 승인 화면의 선택지에도 쓰인다
      queryClient.invalidateQueries({ queryKey: staffKeys.options }),
      queryClient.invalidateQueries({ queryKey: ["admin-employees"] }),
    ]);
}

export function useSaveDepartment(id: string | null) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: DepartmentBody) =>
      id
        ? unwrap(
            api.PATCH("/api/v1/admin/departments/{department_id}", { params: { path: { department_id: id } }, body }),
          )
        : unwrap(api.POST("/api/v1/admin/departments", { body })),
    onSuccess: invalidate,
  });
}

export function useDeleteDepartment() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(api.DELETE("/api/v1/admin/departments/{department_id}", { params: { path: { department_id: id } } })),
    onSuccess: invalidate,
  });
}

/**
 * 팀 저장: 이름·부서·설명을 저장하고 담당 과정을 맞춘다 (과정당 한 팀, A62).
 * 빠진 과정은 담당 팀을 비우고, 더한 과정은 이 팀으로 옮긴다.
 */
export function useSaveTeam(id: string | null) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async ({ body, bootcampIds, before }: { body: TeamBody; bootcampIds: string[]; before: string[] }) => {
      const team = id
        ? await unwrap(api.PATCH("/api/v1/admin/teams/{team_id}", { params: { path: { team_id: id } }, body }))
        : await unwrap(api.POST("/api/v1/admin/teams", { body }));
      const assign = (bootcampId: string, teamId: string | null) =>
        unwrap(
          api.PUT("/api/v1/admin/bootcamps/{bootcamp_id}/team", {
            params: { path: { bootcamp_id: bootcampId } },
            body: { team_id: teamId },
          }),
        );
      for (const removed of before.filter((b) => !bootcampIds.includes(b))) await assign(removed, null);
      for (const added of bootcampIds.filter((b) => !before.includes(b))) await assign(added, team.id);
      return team;
    },
    onSettled: invalidate,
  });
}

export function useDeleteTeam() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, moveTo }: { id: string; moveTo: string | null }) =>
      unwrap(
        api.DELETE("/api/v1/admin/teams/{team_id}", {
          params: { path: { team_id: id }, query: moveTo ? { move_to_team_id: moveTo } : {} },
        }),
      ),
    onSuccess: invalidate,
  });
}
