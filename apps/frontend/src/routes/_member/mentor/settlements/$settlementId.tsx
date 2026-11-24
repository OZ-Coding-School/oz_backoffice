import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { mySettlementQuery } from "@/features/mentor-settlements/api";
import { SettlementPage } from "@/features/mentor-settlements/components/settlement-page";

/** 멘토 정산서 명세 (F54). 마감된 내 정산만 볼 수 있다 (그 밖은 404) */
export const Route = createFileRoute("/_member/mentor/settlements/$settlementId")({
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["MENTOR"], location);
  },
  loader: ({ context, params }) => context.queryClient.prefetchQuery(mySettlementQuery(params.settlementId)),
  component: function MentorSettlement() {
    const { settlementId } = Route.useParams();
    return <SettlementPage settlementId={settlementId} />;
  },
});
