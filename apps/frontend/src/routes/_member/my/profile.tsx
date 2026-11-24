import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { meQuery } from "@/features/auth/api";
import { requireAccount } from "@/features/auth/guards";
import { enrollmentsQuery } from "@/features/member/api";
import { myAssignmentsQuery } from "@/features/mentor-requests/api";
import { mentorProfileQuery } from "@/features/mentor-profile/api";
import { MentorProfilePage } from "@/features/mentor-profile/components/mentor-profile-page";
import { passwordChangeQuery } from "@/features/profile/api";
import { ProfilePage } from "@/features/profile/components/profile-page";

/** 내 정보 (수강생, F37) · 내 프로필 (멘토, F56) */
export const Route = createFileRoute("/_member/my/profile")({
  beforeLoad: async ({ context, location }) => {
    const me = await requireAccount(context.queryClient, ["STUDENT", "MENTOR"], location);
    return { accountType: me.account_type };
  },
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.prefetchQuery(passwordChangeQuery),
      ...(context.accountType === "MENTOR"
        ? [context.queryClient.prefetchQuery(mentorProfileQuery), context.queryClient.prefetchQuery(myAssignmentsQuery)]
        : [context.queryClient.prefetchQuery(enrollmentsQuery)]),
    ]),
  component: function MyProfile() {
    const me = useQuery(meQuery);
    return me.data?.account_type === "MENTOR" ? <MentorProfilePage /> : <ProfilePage />;
  },
});
