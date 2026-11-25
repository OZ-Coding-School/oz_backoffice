import { createFileRoute } from "@tanstack/react-router";

import type { EnrollmentStatus } from "@/features/admin-students/api";
import { StudentsPage, type StudentsSearch } from "@/features/admin-students/components/students-page";
import { ENROLLMENT_ORDER } from "@/features/admin-students/labels";
import { staffAccessQuery } from "@/features/staff/api";

const text = (v: unknown) => (typeof v === "string" && v ? v : undefined);

/** 학사 > 수강생 (F76). 기수 `cohort`(없으면 담당 기수 중 첫 기수), 수강 상태 `status`, 검색 `q` */
export const Route = createFileRoute("/_staff/admin/academy/students/")({
  validateSearch: (search: Record<string, unknown>): StudentsSearch => {
    const out: StudentsSearch = {};
    const cohort = text(search.cohort);
    if (cohort) out.cohort = cohort;
    if (ENROLLMENT_ORDER.includes(search.status as EnrollmentStatus)) out.status = search.status as EnrollmentStatus;
    if (search.group === "status" || search.group === "signup") out.group = search.group;
    const q = text(search.q);
    if (q) out.q = q;
    return out;
  },
  loader: ({ context }) => context.queryClient.prefetchQuery(staffAccessQuery),
  component: function Students() {
    return <StudentsPage search={Route.useSearch()} />;
  },
});
