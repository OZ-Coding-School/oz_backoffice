import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { enrollmentsQuery } from "@/features/member/api";
import { passwordChangeQuery } from "@/features/profile/api";
import { ProfilePage } from "@/features/profile/components/profile-page";

/** 수강생 내 정보 (F37) */
export const Route = createFileRoute("/_member/my/profile")({
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["STUDENT"], location);
  },
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.prefetchQuery(enrollmentsQuery),
      context.queryClient.prefetchQuery(passwordChangeQuery),
    ]),
  component: ProfilePage,
});
