import { infiniteQueryOptions } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type BalanceAccount = components["schemas"]["AccountResponse"];
export type Transaction = components["schemas"]["TransactionResponse"];
export type TransactionType = components["schemas"]["MentoringBalanceTransactionType"];

export const PAGE_SIZE = 20;

export const balanceKeys = {
  transactions: (accountId: string) => ["member", "balances", accountId, "transactions"] as const,
};

/** 계좌 원장 (최신순, 20개씩, 커서 before = 마지막 원장 ID, F38) */
export function transactionsQuery(accountId: string) {
  return infiniteQueryOptions({
    queryKey: balanceKeys.transactions(accountId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/me/balances/{account_id}/transactions", {
          params: {
            path: { account_id: accountId },
            query: { limit: PAGE_SIZE, ...(pageParam ? { before: pageParam } : {}) },
          },
        }),
      ),
    getNextPageParam: (last) => (last.length < PAGE_SIZE ? undefined : (last.at(-1)?.id ?? undefined)),
  });
}
