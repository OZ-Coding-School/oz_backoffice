import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { staffAccessQuery } from "@/features/staff/api";

export type Position = components["schemas"]["PositionResponse"];
export type PermissionDef = components["schemas"]["PermissionDefinitionResponse"];

export const permissionKeys = {
  positions: ["admin-permissions", "positions"] as const,
  definitions: ["admin-permissions", "definitions"] as const,
};

/** 직위 = 역할 (A87): 권한 묶음·데이터 범위·직원 수 */
export const positionsQuery = queryOptions({
  queryKey: permissionKeys.positions,
  queryFn: () => unwrap(api.GET("/api/v1/admin/positions")),
});

/** 권한 정의 (A86): 영역·엔터티·동작 */
export const permissionDefsQuery = queryOptions({
  queryKey: permissionKeys.definitions,
  queryFn: () => unwrap(api.GET("/api/v1/admin/permissions")),
  staleTime: Infinity,
});

/** 직위 권한 묶음 교체 (A87). 내 권한이 바뀔 수 있어 staff-access도 다시 읽는다 */
export function useSavePositionPermissions() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ positionId, permissions }: { positionId: string; permissions: string[] }) =>
      unwrap(
        api.PUT("/api/v1/admin/positions/{position_id}/permissions", {
          params: { path: { position_id: positionId } },
          body: { permissions },
        }),
      ),
    onSuccess: (saved) => {
      client.setQueryData(permissionKeys.positions, (old: Position[] | undefined) =>
        old?.map((p) => (p.id === saved.id ? saved : p)),
      );
      void client.invalidateQueries({ queryKey: staffAccessQuery.queryKey });
    },
  });
}
