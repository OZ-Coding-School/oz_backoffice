import { createFileRoute } from "@tanstack/react-router";

import { permissionDefsQuery, positionsQuery } from "@/features/admin-permissions/api";
import { PermissionsPage } from "@/features/admin-permissions/components/permissions-page";

export interface PermissionsSearch {
  position?: string;
}

/** 조직 설정 > 권한 (F65). 고른 직위 `position`(없으면 첫 직위) */
export const Route = createFileRoute("/_staff/admin/org/permissions")({
  validateSearch: (search: Record<string, unknown>): PermissionsSearch =>
    typeof search.position === "string" && search.position ? { position: search.position } : {},
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.prefetchQuery(positionsQuery),
      context.queryClient.prefetchQuery(permissionDefsQuery),
    ]),
  component: function Permissions() {
    return <PermissionsPage positionId={Route.useSearch().position} />;
  },
});
