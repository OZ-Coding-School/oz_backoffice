import { createFileRoute } from "@tanstack/react-router";

import { bootcampsQuery } from "@/features/admin-academy/api";
import { BootcampsPage, type BootcampsSearch } from "@/features/admin-academy/components/bootcamps-page";

const text = (v: unknown) => (typeof v === "string" && v ? v : undefined);

/** 학사 > 과정·기수 (F74). 과정 `bootcamp`(없으면 첫 과정), 기수 패널 `cohort`, 과정 패널 `panel=bootcamp` */
export const Route = createFileRoute("/_staff/admin/academy/bootcamps")({
  validateSearch: (search: Record<string, unknown>): BootcampsSearch => {
    const out: BootcampsSearch = {};
    const bootcamp = text(search.bootcamp);
    if (bootcamp) out.bootcamp = bootcamp;
    const cohort = text(search.cohort);
    if (cohort) out.cohort = cohort;
    if (search.panel === "bootcamp") out.panel = "bootcamp";
    return out;
  },
  loader: ({ context }) => context.queryClient.prefetchQuery(bootcampsQuery),
  component: function Bootcamps() {
    return <BootcampsPage search={Route.useSearch()} />;
  },
});
