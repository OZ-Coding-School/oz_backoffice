import { createFileRoute } from "@tanstack/react-router";

import { MembersPage, type MembersSearch } from "@/features/admin-members/components/members-page";

const text = (v: unknown) => (typeof v === "string" && v ? v : undefined);

/** 회원 관리 > 전체 회원 (F71). 종류 `tab`, 검색 `q`, 상태 `status`, 패널 `user` */
export const Route = createFileRoute("/_staff/admin/members/users")({
  validateSearch: (search: Record<string, unknown>): MembersSearch => {
    const out: MembersSearch = {};
    if (search.tab === "student" || search.tab === "mentor" || search.tab === "staff") out.tab = search.tab;
    if (search.status === "active" || search.status === "inactive") out.status = search.status;
    const q = text(search.q);
    if (q) out.q = q;
    const user = text(search.user);
    if (user) out.user = user;
    return out;
  },
  component: function Members() {
    return <MembersPage search={Route.useSearch()} />;
  },
});
