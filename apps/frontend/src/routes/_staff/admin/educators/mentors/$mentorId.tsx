import { createFileRoute } from "@tanstack/react-router";

import { mentorQuery } from "@/features/admin-mentors/api";
import { MentorPage } from "@/features/admin-mentors/components/mentor-page";

interface MentorSearch {
  tab?: "assignments";
}

/** 강사·멘토 > 멘토 상세 (F79). 탭 `tab=assignments` (없으면 프로필) */
export const Route = createFileRoute("/_staff/admin/educators/mentors/$mentorId")({
  validateSearch: (search: Record<string, unknown>): MentorSearch =>
    search.tab === "assignments" ? { tab: "assignments" } : {},
  loader: ({ context, params }) => context.queryClient.prefetchQuery(mentorQuery(params.mentorId)),
  component: function Mentor() {
    const { mentorId } = Route.useParams();
    const { tab } = Route.useSearch();
    return <MentorPage mentorId={mentorId} tab={tab ?? "profile"} />;
  },
});
