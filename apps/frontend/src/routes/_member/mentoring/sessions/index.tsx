import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { isSessionTab, mySessionsQuery, type SessionTab } from "@/features/sessions/api";
import { SessionsPage } from "@/features/sessions/components/sessions-page";

/** 수강생 진행 기록 (F33). 탭은 검색 파라미터 `tab`(all·scheduled·completed·canceled·no_show). */
export const Route = createFileRoute("/_member/mentoring/sessions/")({
  validateSearch: (search: Record<string, unknown>): { tab?: SessionTab } =>
    isSessionTab(search.tab) && search.tab !== "all" ? { tab: search.tab } : {},
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["STUDENT"], location);
  },
  loaderDeps: ({ search }) => ({ tab: search.tab ?? "all" }),
  loader: ({ context, deps }) => context.queryClient.prefetchInfiniteQuery(mySessionsQuery(deps.tab)),
  component: function Sessions() {
    const { tab } = Route.useSearch();
    return <SessionsPage tab={tab ?? "all"} />;
  },
});
