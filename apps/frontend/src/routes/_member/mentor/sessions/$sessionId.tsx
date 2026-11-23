import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { noteQuery } from "@/features/mentor-sessions/api";
import { MentorSessionPage } from "@/features/mentor-sessions/components/mentor-session-page";
import { sessionQuery } from "@/features/sessions/api";

/** 멘토 세션 상세 (F48). 담당 멘토만 볼 수 있다 (그 밖은 404) */
export const Route = createFileRoute("/_member/mentor/sessions/$sessionId")({
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["MENTOR"], location);
  },
  loader: ({ context, params }) =>
    Promise.all([
      context.queryClient.prefetchQuery(sessionQuery(params.sessionId)),
      context.queryClient.prefetchQuery(noteQuery(params.sessionId)),
    ]),
  component: function MentorSession() {
    const { sessionId } = Route.useParams();
    return <MentorSessionPage sessionId={sessionId} />;
  },
});
