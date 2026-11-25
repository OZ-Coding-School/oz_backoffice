import { createFileRoute } from "@tanstack/react-router";

import { positionsQuery } from "@/features/admin-permissions/api";
import { PositionsPage } from "@/features/admin-positions/components/positions-page";

export interface PositionsSearch {
  position?: string;
}

/** 조직 설정 > 직위 (F70). 패널로 연 직위 `position` */
export const Route = createFileRoute("/_staff/admin/org/positions")({
  validateSearch: (search: Record<string, unknown>): PositionsSearch =>
    typeof search.position === "string" && search.position ? { position: search.position } : {},
  loader: ({ context }) => context.queryClient.prefetchQuery(positionsQuery),
  component: function Positions() {
    return <PositionsPage positionId={Route.useSearch().position} />;
  },
});
