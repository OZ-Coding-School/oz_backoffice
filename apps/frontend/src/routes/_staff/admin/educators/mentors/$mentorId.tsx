import { createFileRoute } from "@tanstack/react-router";

import { mentorQuery } from "@/features/admin-mentors/api";
import { MentorPage } from "@/features/admin-mentors/components/mentor-page";

const DATE_KEY = /^\d{4}-\d{2}-\d{2}$/;

interface MentorSearch {
  tab?: "assignments" | "schedule" | "contracts";
  /** 일정 탭의 주 (그 주의 아무 날) */
  week?: string;
  /** 배정 패널: 배정 id 또는 new (F85) */
  assignment?: string;
}

/** 강사·멘토 > 멘토 상세 (F79·F83). 탭 `tab=assignments|contracts` (없으면 프로필) */
export const Route = createFileRoute("/_staff/admin/educators/mentors/$mentorId")({
  validateSearch: (search: Record<string, unknown>): MentorSearch => {
    const out: MentorSearch = {};
    if (search.tab === "assignments" || search.tab === "schedule" || search.tab === "contracts") out.tab = search.tab;
    if (out.tab === "schedule" && typeof search.week === "string" && DATE_KEY.test(search.week)) out.week = search.week;
    if (out.tab === "assignments" && typeof search.assignment === "string" && search.assignment)
      out.assignment = search.assignment;
    return out;
  },
  loader: ({ context, params }) => context.queryClient.prefetchQuery(mentorQuery(params.mentorId)),
  component: function Mentor() {
    const { mentorId } = Route.useParams();
    const { tab, assignment, week } = Route.useSearch();
    return <MentorPage mentorId={mentorId} tab={tab ?? "profile"} assignment={assignment} week={week} />;
  },
});
