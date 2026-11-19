import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { requestQuery } from "@/features/requests/api";
import { ChangeRequestPage } from "@/features/requests/components/change-request-page";

/** 신청 변경 (F32): 기존 신청 취소 + 같은 대상의 새 신청 */
export const Route = createFileRoute("/_member/mentoring/requests/$requestId_/change")({
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["STUDENT"], location);
  },
  loader: ({ context, params }) => context.queryClient.prefetchQuery(requestQuery(params.requestId)),
  component: function ChangeRequest() {
    const { requestId } = Route.useParams();
    return <ChangeRequestPage requestId={requestId} />;
  },
});
