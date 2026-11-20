import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Wallet } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LoadMore } from "@/components/load-more";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { balancesQuery } from "@/features/requests/api";
import { formatKst, formatMinutes } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { transactionsQuery, type BalanceAccount, type Transaction } from "../api";
import { accountLabel, accountSummary, deltaText, remainingDelta, sortAccounts, typeLabel } from "../labels";

/** 시간 지급·차감 내역 (Figma `Column / 시간 지급·차감 내역 (FE-6b)`, F36·F38) */
export function BalancesPage({ accountId }: { accountId: string | undefined }) {
  const balances = useQuery(balancesQuery);
  const accounts = sortAccounts(balances.data ?? []);
  const selected = accounts.find((a) => a.id === accountId) ?? accounts[0];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">시간 지급·차감 내역</h1>
        <p className="text-body text-muted-foreground">멘토링 시간이 언제 지급되고 쓰였는지 보여 줘요.</p>
      </div>
      {balances.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : balances.isError ? (
        <ErrorState onRetry={() => void balances.refetch()} />
      ) : !selected ? (
        <EmptyState
          icon={Wallet}
          title="아직 받은 멘토링 시간이 없어요"
          description="운영진이 시간을 지급하면 여기에서 볼 수 있어요."
        />
      ) : (
        <>
          <nav aria-label="계좌" className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
            <ul className="flex gap-3 md:grid md:grid-cols-2">
              {accounts.map((a) => (
                <li key={a.id} className="w-65 shrink-0 md:w-auto">
                  <AccountCard account={a} active={a.id === selected.id} />
                </li>
              ))}
            </ul>
          </nav>
          <Ledger key={selected.id} accountId={selected.id} />
        </>
      )}
    </div>
  );
}

function AccountCard({ account, active }: { account: BalanceAccount; active: boolean }) {
  return (
    <Link
      to="/mentoring/balances"
      search={{ account: account.id }}
      replace
      aria-current={active ? "true" : undefined}
      className={cn(
        "flex h-full flex-col gap-1 rounded-xl border bg-card px-4 py-4 outline-none focus-visible:ring-2 focus-visible:ring-ring md:px-5",
        active ? "border-2 border-primary" : "border-border hover:bg-muted",
      )}
    >
      <span className="flex items-center gap-2 text-caption text-muted-foreground">
        {accountLabel(account)}
        {account.is_expired ? <Badge variant="secondary">만료</Badge> : null}
      </span>
      <span className="text-h1 text-foreground">{formatMinutes(account.remaining_minutes)}</span>
      <span className="text-caption text-muted-foreground">{accountSummary(account)}</span>
    </Link>
  );
}

function Ledger({ accountId }: { accountId: string }) {
  const list = useInfiniteQuery(transactionsQuery(accountId));
  const items = list.data?.pages.flat() ?? [];
  if (list.isPending) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }
  if (list.isError) return <ErrorState onRetry={() => void list.refetch()} />;
  if (items.length === 0) return <EmptyState icon={Wallet} title="아직 내역이 없어요" />;
  return (
    <section aria-label="내역" className="overflow-hidden rounded-xl border border-border bg-card">
      {/* 태블릿·데스크톱: 표 */}
      <table className="hidden w-full text-left md:table">
        <thead className="bg-muted text-caption text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2.5 font-normal">
              일시
            </th>
            <th scope="col" className="px-4 py-2.5 font-normal">
              유형
            </th>
            <th scope="col" className="px-4 py-2.5 font-normal">
              변동
            </th>
            <th scope="col" className="px-4 py-2.5 font-normal">
              남은 시간
            </th>
            <th scope="col" className="px-4 py-2.5 font-normal">
              내용
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((tx) => (
            <tr key={tx.id} className="text-body text-foreground">
              <td className="px-4 py-3.5 whitespace-nowrap">
                {tx.created_at ? formatKst(tx.created_at, "MM/dd HH:mm") : "-"}
              </td>
              <td className="px-4 py-3.5">
                <TypeBadge tx={tx} />
              </td>
              <td className="px-4 py-3.5 whitespace-nowrap">
                <Delta tx={tx} />
              </td>
              <td className="px-4 py-3.5 whitespace-nowrap">{formatMinutes(tx.after_remaining)}</td>
              <td className="px-4 py-3.5">{tx.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {/* 휴대폰: 행 카드 */}
      <ul className="divide-y divide-border md:hidden">
        {items.map((tx) => (
          <li key={tx.id} className="flex flex-col gap-1 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2 text-body text-foreground">
              <span>{tx.created_at ? formatKst(tx.created_at, "MM/dd HH:mm") : "-"}</span>
              <TypeBadge tx={tx} />
              <Delta tx={tx} />
            </div>
            <div className="flex items-center gap-2 text-body-sm">
              <span className="min-w-0 flex-1 text-foreground">{tx.reason}</span>
              <span className="shrink-0 text-muted-foreground">남은 {formatMinutes(tx.after_remaining)}</span>
            </div>
          </li>
        ))}
      </ul>
      {list.hasNextPage ? (
        <LoadMore
          loading={list.isFetchingNextPage}
          label="이전 내역을 불러오는 중…"
          onVisible={() => void list.fetchNextPage()}
        />
      ) : null}
    </section>
  );
}

function TypeBadge({ tx }: { tx: Transaction }) {
  const { label, badge } = typeLabel(tx);
  return <Badge variant={badge}>{label}</Badge>;
}

function Delta({ tx }: { tx: Transaction }) {
  const delta = remainingDelta(tx);
  // F14: 상태 색은 배지에만. 늘어난 시간만 success 글자색(시안)으로 구분한다
  return <span className={cn(delta !== null && delta > 0 && "text-success-text")}>{deltaText(tx)}</span>;
}
