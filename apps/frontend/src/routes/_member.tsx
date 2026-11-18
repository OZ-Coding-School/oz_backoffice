import { createFileRoute, Outlet } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";

/** 승인된 수강생·멘토만 들어온다 (F20). */
export const Route = createFileRoute("/_member")({
  beforeLoad: async ({ context, location }) => ({
    me: await requireAccount(context.queryClient, ["STUDENT", "MENTOR"], location),
  }),
  component: Outlet,
});
