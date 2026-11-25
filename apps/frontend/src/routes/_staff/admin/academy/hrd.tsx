import { createFileRoute } from "@tanstack/react-router";

import { hrdBootcampsQuery } from "@/features/admin-academy/api";
import { HrdPage, type HrdSearch } from "@/features/admin-academy/components/hrd-page";

const text = (v: unknown) => (typeof v === "string" && v ? v : undefined);

/** 학사 > HRD 과정 (F75). HRD 과정 패널 `hrd`, 회차 패널 `cohort` */
export const Route = createFileRoute("/_staff/admin/academy/hrd")({
  validateSearch: (search: Record<string, unknown>): HrdSearch => {
    const out: HrdSearch = {};
    const hrd = text(search.hrd);
    if (hrd) out.hrd = hrd;
    const cohort = text(search.cohort);
    if (hrd && cohort) out.cohort = cohort;
    return out;
  },
  loader: ({ context }) => context.queryClient.prefetchQuery(hrdBootcampsQuery),
  component: function Hrd() {
    return <HrdPage search={Route.useSearch()} />;
  },
});
