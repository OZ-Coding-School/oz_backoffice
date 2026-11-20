import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { sessionQuery } from "@/features/sessions/api";
import { SessionDetailPage } from "@/features/sessions/components/session-detail-page";

/** 수강생 세션 상세 (F33·F34) */
export const Route = createFileRoute("/_member/mentoring/sessions/$sessionId")({
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["STUDENT"], location);
  },
  loader: ({ context, params }) => context.queryClient.prefetchQuery(sessionQuery(params.sessionId)),
  component: function SessionDetail() {
    const { sessionId } = Route.useParams();
    return <SessionDetailPage sessionId={sessionId} />;
  },
});
