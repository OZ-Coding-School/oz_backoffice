import { createFileRoute, redirect } from "@tanstack/react-router";

import { studentQuery } from "@/features/admin-students/api";
import { StudentPage, type StudentTab } from "@/features/admin-students/components/student-page";

interface StudentSearch {
  cohort: string;
  tab?: StudentTab;
}

/** 학사 > 수강생 상세 (F76). 기수 `cohort`(기수 범위 권한 확인에 필요), 탭 `tab=mentoring` */
export const Route = createFileRoute("/_staff/admin/academy/students/$studentId")({
  validateSearch: (search: Record<string, unknown>): StudentSearch => ({
    cohort: typeof search.cohort === "string" ? search.cohort : "",
    ...(search.tab === "mentoring" ? { tab: "mentoring" as const } : {}),
  }),
  beforeLoad: ({ search }) => {
    if (!search.cohort) throw redirect({ to: "/admin/academy/students" });
  },
  loaderDeps: ({ search }) => ({ cohort: search.cohort }),
  loader: ({ context, params, deps }) => context.queryClient.prefetchQuery(studentQuery(deps.cohort, params.studentId)),
  component: function Student() {
    const { studentId } = Route.useParams();
    const { cohort, tab } = Route.useSearch();
    return <StudentPage studentId={studentId} cohortId={cohort} tab={tab ?? "basic"} />;
  },
});
