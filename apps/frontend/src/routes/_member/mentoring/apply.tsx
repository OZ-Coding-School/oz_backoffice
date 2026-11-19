import { createFileRoute } from "@tanstack/react-router";

import { ApplyPage, type ApplyStep } from "@/features/apply/components/apply-page";
import { requireAccount } from "@/features/auth/guards";

const STEPS: readonly ApplyStep[] = ["mentor", "schedule", "content", "confirm", "done"];

/** 1:1 멘토링 신청 (F30): 단계는 `step`, 완료는 `step=done&id=` */
export const Route = createFileRoute("/_member/mentoring/apply")({
  validateSearch: (search: Record<string, unknown>): { step?: Exclude<ApplyStep, "mentor">; id?: string } => {
    const step = STEPS.find((s) => s === search.step);
    return {
      ...(step && step !== "mentor" ? { step } : {}),
      ...(typeof search.id === "string" ? { id: search.id } : {}),
    };
  },
  beforeLoad: async ({ context, location }) => ({
    me: await requireAccount(context.queryClient, ["STUDENT"], location),
  }),
  component: function Apply() {
    const { step, id } = Route.useSearch();
    const { me } = Route.useRouteContext();
    return <ApplyPage userId={me.id} step={step ?? "mentor"} {...(id ? { requestId: id } : {})} />;
  },
});
