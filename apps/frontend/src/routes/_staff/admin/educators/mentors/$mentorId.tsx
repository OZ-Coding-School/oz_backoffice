import { createFileRoute } from "@tanstack/react-router";

import { mentorQuery } from "@/features/admin-mentors/api";
import { MentorPage } from "@/features/admin-mentors/components/mentor-page";

interface MentorSearch {
  tab?: "assignments" | "contracts";
  /** 배정 패널: 배정 id 또는 new (F85) */
  assignment?: string;
}

/** 강사·멘토 > 멘토 상세 (F79·F83). 탭 `tab=assignments|contracts` (없으면 프로필) */
export const Route = createFileRoute("/_staff/admin/educators/mentors/$mentorId")({
  validateSearch: (search: Record<string, unknown>): MentorSearch => {
    const out: MentorSearch = {};
    if (search.tab === "assignments" || search.tab === "contracts") out.tab = search.tab;
    if (out.tab === "assignments" && typeof search.assignment === "string" && search.assignment)
      out.assignment = search.assignment;
    return out;
  },
  loader: ({ context, params }) => context.queryClient.prefetchQuery(mentorQuery(params.mentorId)),
  component: function Mentor() {
    const { mentorId } = Route.useParams();
    const { tab, assignment } = Route.useSearch();
    return <MentorPage mentorId={mentorId} tab={tab ?? "profile"} assignment={assignment} />;
  },
});
