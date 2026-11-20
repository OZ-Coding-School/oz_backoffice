import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { transactionsQuery } from "@/features/balances/api";
import { BalancesPage } from "@/features/balances/components/balances-page";
import { sortAccounts } from "@/features/balances/labels";
import { balancesQuery } from "@/features/requests/api";

/** 수강생 시간 지급·차감 내역 (F38). 계좌는 검색 파라미터 `account`(없으면 1:1 계좌) */
export const Route = createFileRoute("/_member/mentoring/balances")({
  validateSearch: (search: Record<string, unknown>): { account?: string } =>
    typeof search.account === "string" ? { account: search.account } : {},
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["STUDENT"], location);
  },
  loaderDeps: ({ search }) => ({ account: search.account }),
  // 계좌 목록을 받은 뒤 고른 계좌(없으면 첫 계좌)의 원장까지 미리 불러온다
  loader: async ({ context, deps }) => {
    const accounts = await context.queryClient.ensureQueryData(balancesQuery).catch(() => []);
    const selected = sortAccounts(accounts).find((a) => a.id === deps.account) ?? sortAccounts(accounts)[0];
    if (selected) await context.queryClient.prefetchInfiniteQuery(transactionsQuery(selected.id));
  },
  component: function Balances() {
    const { account } = Route.useSearch();
    return <BalancesPage accountId={account} />;
  },
});
