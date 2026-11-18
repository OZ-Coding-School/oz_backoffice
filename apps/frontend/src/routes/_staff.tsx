import { createFileRoute, Outlet } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";

/** 승인된 운영진만 들어온다 (F20). */
export const Route = createFileRoute("/_staff")({
  beforeLoad: async ({ context, location }) => ({
    me: await requireAccount(context.queryClient, ["STAFF"], location),
  }),
  component: Outlet,
});
