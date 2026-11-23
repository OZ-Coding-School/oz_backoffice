import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { ReceivedRequestPage } from "@/features/mentor-requests/components/received-request-page";
import { requestQuery } from "@/features/requests/api";

/** 멘토 받은 신청 상세 (F45). 담당 멘토만 볼 수 있다 (그 밖은 404, A66) */
export const Route = createFileRoute("/_member/mentor/requests/$requestId")({
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["MENTOR"], location);
  },
  loader: ({ context, params }) => context.queryClient.prefetchQuery(requestQuery(params.requestId)),
  component: function ReceivedRequest() {
    const { requestId } = Route.useParams();
    return <ReceivedRequestPage requestId={requestId} />;
  },
});
