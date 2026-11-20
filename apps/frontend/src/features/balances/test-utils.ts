import { http, HttpResponse } from "msw";

import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";

import type { BalanceAccount, Transaction } from "./api";

export function makeAccount(overrides: Partial<BalanceAccount> = {}): BalanceAccount {
  return {
    id: "a1",
    owner_type: "STUDENT",
    owner_id: "st12",
    owner_name: "가수강",
    valid_from: "2026-10-01",
    valid_until: "2027-01-31",
    is_expired: false,
    total_minutes: 360,
    held_minutes: 60,
    used_minutes: 90,
    remaining_minutes: 210,
    ...overrides,
  };
}

/** Figma와 같은 내역 (최신순): 0 → +240 → +120 → 차감 예정 −60 → 차감 확정 → 추가 차감 −30 → 차감 예정 −60 */
export const LEDGER: Transaction[] = [
  tx("t6", "HOLD", 60, 210, "멘토링 신청", "2026-11-16T01:02:00Z"),
  tx("t5", "OVERTIME", 30, 270, "실제 진행 시간이 신청보다 김", "2026-11-15T02:20:00Z"),
  tx("t4", "USING", 60, 300, "멘토링 승인", "2026-11-14T13:30:00Z"),
  tx("t3", "HOLD", 60, 300, "멘토링 신청", "2026-11-14T12:10:00Z"),
  tx("t2", "STAFF_GRANT", 120, 360, "11월 추가 멘토링 시간", "2026-11-10T02:00:00Z"),
  tx("t1", "STAFF_GRANT", 240, 240, "기본 지급", "2026-10-31T15:00:00Z"),
];

export function tx(
  id: string,
  type: Transaction["type"],
  amount: number,
  afterRemaining: number,
  reason: string,
  createdAt: string,
): Transaction {
  return { id, type, amount, after_remaining: afterRemaining, after_held: 0, reason, created_at: createdAt };
}

/** 계좌 목록과 계좌별 원장 (before 커서로 나눈다) */
export function mockBalances(accounts: BalanceAccount[], ledgers: Record<string, Transaction[]>) {
  const seen: { account: string; before: string | null }[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/balances"), () => HttpResponse.json(accounts)),
    http.get(apiUrl("/api/v1/me/balances/{account_id}/transactions"), ({ params, request }) => {
      const url = new URL(request.url);
      const before = url.searchParams.get("before");
      const limit = Number(url.searchParams.get("limit") ?? 50);
      const all = ledgers[String(params.account_id)] ?? [];
      seen.push({ account: String(params.account_id), before });
      const start = before ? all.findIndex((t) => t.id === before) + 1 : 0;
      return HttpResponse.json(all.slice(start, start + limit));
    }),
  );
  return seen;
}
