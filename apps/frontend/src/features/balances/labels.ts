import type { BadgeProps } from "@/components/ui/badge";
import { formatMinutes } from "@/lib/datetime";

import type { BalanceAccount, Transaction, TransactionType } from "./api";

type Tone = NonNullable<BadgeProps["variant"]>;

/** 원장 유형 (F36: 사용자 용어). 조정은 음수면 '회수' */
const TYPE: Record<TransactionType, { label: string; badge: Tone }> = {
  STAFF_GRANT: { label: "지급", badge: "success" },
  STAFF_ADJUST: { label: "조정", badge: "secondary" },
  HOLD: { label: "차감 예정", badge: "warning" },
  RELEASE: { label: "차감 예정 취소", badge: "outline" },
  USING: { label: "차감", badge: "default" },
  REFUND: { label: "돌려받음", badge: "info" },
  OVERTIME: { label: "추가 차감", badge: "destructive" },
};

export function typeLabel(tx: Pick<Transaction, "type" | "amount">): { label: string; badge: Tone } {
  if (tx.type === "STAFF_ADJUST" && tx.amount < 0) return { label: "회수", badge: "secondary" };
  return TYPE[tx.type];
}

/**
 * 남은 시간의 변동(분, F38). 차감(USING)은 차감 예정이던 시간을 확정할 뿐 남은 시간이 그대로라 null.
 * 원장 amount는 조정만 음수가 될 수 있고 나머지는 양수다.
 */
export function remainingDelta(tx: Pick<Transaction, "type" | "amount">): number | null {
  switch (tx.type) {
    case "STAFF_GRANT":
    case "RELEASE":
    case "REFUND":
      return tx.amount;
    case "HOLD":
    case "OVERTIME":
      return -tx.amount;
    case "STAFF_ADJUST":
      return tx.amount;
    case "USING":
      return null;
  }
}

/** "−60분" / "+120분" / "— · 확정 60분" */
export function deltaText(tx: Pick<Transaction, "type" | "amount">): string {
  const delta = remainingDelta(tx);
  if (delta === null) return `— · 확정 ${formatMinutes(tx.amount)}`;
  return `${delta >= 0 ? "+" : "−"}${Math.abs(delta)}분`;
}

/** 계좌 이름: "1:1 계좌" / "3팀 알파 계좌" */
export function accountLabel(account: Pick<BalanceAccount, "owner_type" | "owner_name">): string {
  return account.owner_type === "STUDENT" ? "1:1 계좌" : `${account.owner_name} 계좌`;
}

/** "차감 예정 1시간 · 사용 1시간 30분 · 01/31까지" */
export function accountSummary(account: BalanceAccount): string {
  const until = account.valid_until.slice(5).replace("-", "/");
  return `차감 예정 ${formatMinutes(account.held_minutes)} · 사용 ${formatMinutes(account.used_minutes)} · ${until}까지`;
}

/** 계좌 순서 (F38): 사용 중 → 만료, 그 안에서 1:1 → 팀 */
export function sortAccounts(accounts: readonly BalanceAccount[]): BalanceAccount[] {
  const rank = (a: BalanceAccount) => (a.is_expired ? 2 : 0) + (a.owner_type === "STUDENT" ? 0 : 1);
  return [...accounts].sort((a, b) => rank(a) - rank(b));
}
