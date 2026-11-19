import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { requestQuery } from "@/features/requests/api";
import { RequestDetailPage } from "@/features/requests/components/request-detail-page";

/** 수강생 신청 상세 (A66·F29) */
export const Route = createFileRoute("/_member/mentoring/requests/$requestId")({
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["STUDENT"], location);
  },
  loader: ({ context, params }) => context.queryClient.prefetchQuery(requestQuery(params.requestId)),
  component: function RequestDetail() {
    const { requestId } = Route.useParams();
    return <RequestDetailPage requestId={requestId} />;
  },
});
