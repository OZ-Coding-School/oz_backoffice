import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { permissionKeys, type Position } from "@/features/admin-permissions/api";
import { staffKeys } from "@/features/auth/staff-api";
import { staffAccessQuery } from "@/features/staff/api";

export type PositionBody = components["schemas"]["PositionCreateRequest"];

function useInvalidate() {
  const client = useQueryClient();
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: permissionKeys.positions }),
      // 직위 이름·담당 방식은 가입·직원 화면의 선택지에도 쓰인다
      client.invalidateQueries({ queryKey: staffKeys.options }),
      client.invalidateQueries({ queryKey: ["admin-employees"] }),
      client.invalidateQueries({ queryKey: ["admin-org"] }),
      client.invalidateQueries({ queryKey: staffAccessQuery.queryKey }),
    ]);
}

/** 직위 추가·수정 (F70). 추가는 맨 아래 순서 */
export function useSavePosition(id: string | null) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: PositionBody) =>
      id
        ? unwrap(
            api.PATCH("/api/v1/admin/positions/{position_id}", {
              params: { path: { position_id: id } },
              body: { name: body.name, assignment_scope: body.assignment_scope ?? null, data_scope: body.data_scope },
            }),
          )
        : unwrap(api.POST("/api/v1/admin/positions", { body })),
    onSettled: invalidate,
  });
}

export function useDeletePosition() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) =>
      unwrap(api.DELETE("/api/v1/admin/positions/{position_id}", { params: { path: { position_id: id } } })),
    onSuccess: invalidate,
  });
}

/** 순서 저장: 순서가 바뀐 직위만 priority를 고친다 (F70) */
export function useReorderPositions() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: async (changes: { id: string; priority: number }[]) => {
      for (const c of changes)
        await unwrap(
          api.PATCH("/api/v1/admin/positions/{position_id}", {
            params: { path: { position_id: c.id } },
            body: { priority: c.priority },
          }),
        );
    },
    onSettled: invalidate,
  });
}

export type { Position };
