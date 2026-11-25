import { createFileRoute } from "@tanstack/react-router";

import { MentorsPage, type MentorsSearch } from "@/features/admin-mentors/components/mentors-page";

/** 강사·멘토 > 멘토 (F79). 검색 `q`, 상태 `status` */
export const Route = createFileRoute("/_staff/admin/educators/mentors/")({
  validateSearch: (search: Record<string, unknown>): MentorsSearch => {
    const out: MentorsSearch = {};
    if (typeof search.q === "string" && search.q) out.q = search.q;
    if (search.status === "active" || search.status === "inactive") out.status = search.status;
    return out;
  },
  component: function Mentors() {
    return <MentorsPage search={Route.useSearch()} />;
  },
});
