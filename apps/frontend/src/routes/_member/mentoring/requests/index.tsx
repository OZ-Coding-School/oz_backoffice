import { createFileRoute } from "@tanstack/react-router";

import { isRequestTab, myRequestsQuery, type RequestTab } from "@/features/requests/api";
import { RequestsPage } from "@/features/requests/components/requests-page";
import { requireAccount } from "@/features/auth/guards";

/** 수강생 신청 내역 (F29). 탭은 검색 파라미터 `tab`(all·pending·approved·closed). */
export const Route = createFileRoute("/_member/mentoring/requests/")({
  validateSearch: (search: Record<string, unknown>): { tab?: RequestTab } =>
    isRequestTab(search.tab) && search.tab !== "all" ? { tab: search.tab } : {},
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["STUDENT"], location);
  },
  loaderDeps: ({ search }) => ({ tab: search.tab ?? "all" }),
  loader: ({ context, deps }) => context.queryClient.prefetchInfiniteQuery(myRequestsQuery(deps.tab)),
  component: function Requests() {
    const { tab } = Route.useSearch();
    return <RequestsPage tab={tab ?? "all"} />;
  },
});
