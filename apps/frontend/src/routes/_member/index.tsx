import { createFileRoute } from "@tanstack/react-router";

import { MemberHome } from "@/features/member/components/member-home";

export const Route = createFileRoute("/_member/")({
  component: function Home() {
    const { me } = Route.useRouteContext();
    return <MemberHome me={me} />;
  },
});
