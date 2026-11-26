import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronRight, Wallet } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Spinner } from "@/components/ui/spinner";
import { CohortSelect } from "@/features/mentor-requests/components/cohort-select";
import { formatMinutes } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { mySettlementsQuery, type SettlementSummary } from "../api";
import { closedLabel, cohortLabel, summaryCards, won } from "../labels";

/** 멘토 정산 목록 (Figma `Group / 정산 · 목록·상세 (FE-12a)`, F54·A55·A56). 데스크톱은 표, 그 밖은 카드 */
export function SettlementsPage({ cohortId }: { cohortId: string | undefined }) {
  const list = useQuery(mySettlementsQuery);
  const navigate = useNavigate();
  const [now] = useState(() => Date.now());
  const all = list.data ?? [];
  const items = cohortId ? all.filter((s) => s.cohort_id === cohortId) : all;
  const cards = summaryCards(items, now);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        icon={Wallet}
        title="정산"
        description="운영진이 마감한 정산만 보여 줘요."
        actions={
          <CohortSelect
            value={cohortId}
            onChange={(cohort) => void navigate({ to: "/mentor/settlements", search: cohort ? { cohort } : {} })}
          />
        }
      />
      {list.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : list.isError ? (
        <ErrorState onRetry={() => void list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Wallet}
          title={all.length === 0 ? "아직 마감된 정산이 없어요" : "이 기수의 정산이 없어요"}
          description={all.length === 0 ? "운영진이 정산을 마감하면 여기에 보여요." : undefined}
        />
      ) : (
        <>
          <ul aria-label="정산 요약" className="grid gap-2.5 md:grid-cols-3 md:gap-4">
            {cards.map((c) => (
              <li
                key={c.label}
                className="flex flex-col gap-1 rounded-2xl border border-border bg-card shadow-sm p-4 md:p-5"
              >
                <span className="flex items-center gap-2 text-caption text-muted-foreground">
                  <span className="inline-flex size-6 items-center justify-center rounded-lg bg-sidebar-accent text-sidebar-accent-foreground">
                    <Wallet aria-hidden className="size-3.5" />
                  </span>
                  {c.label}
                </span>
                <span className="text-h2 text-foreground">{won(c.amount)}</span>
                <span className="text-caption text-muted-foreground">{c.note}</span>
              </li>
            ))}
          </ul>
          <SettlementTable items={items} />
          <ul className="flex flex-col gap-2.5 lg:hidden">
            {items.map((s) => (
              <li key={s.id}>
                <SettlementCard settlement={s} />
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/** 제목 링크의 누름 영역을 행·카드 전체로 넓힌다 */
const STRETCHED = "outline-none after:absolute after:inset-0 after:rounded-xl focus-visible:underline hover:underline";

function title(s: SettlementSummary): string {
  return cohortLabel(s) ?? "기수 정보 없음";
}

function SettlementTable({ items }: { items: SettlementSummary[] }) {
  return (
    <div className="hidden overflow-hidden rounded-2xl border border-border bg-card shadow-sm lg:block">
      <table className="w-full text-left">
        <thead className="bg-muted text-caption text-muted-foreground">
          <tr>
            <th scope="col" className="w-32 px-4 py-2.5 font-normal">
              정산 월
            </th>
            <th scope="col" className="px-4 py-2.5 font-normal">
              기수
            </th>
            <th scope="col" className="w-24 px-4 py-2.5 text-right font-normal">
              세션
            </th>
            <th scope="col" className="w-32 px-4 py-2.5 text-right font-normal">
              정산 시간
            </th>
            <th scope="col" className="w-36 px-4 py-2.5 text-right font-normal">
              금액
            </th>
            <th scope="col" className="w-28 px-4 py-2.5 font-normal">
              마감
            </th>
            <th scope="col" className="w-12 px-4 py-2.5">
              <span className="sr-only">보기</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.id} className="relative border-t border-border text-body hover:bg-muted">
              <td className="px-4 py-3 text-foreground">{s.month}</td>
              <td className="px-4 py-3">
                <Link
                  to="/mentor/settlements/$settlementId"
                  params={{ settlementId: s.id }}
                  className={cn("text-body-strong text-foreground", STRETCHED)}
                >
                  {title(s)}
                </Link>
              </td>
              <td className="px-4 py-3 text-right text-foreground">{s.session_count}회</td>
              <td className="px-4 py-3 text-right text-foreground">{formatMinutes(s.total_minutes)}</td>
              <td className="px-4 py-3 text-right text-foreground">{won(s.total_amount)}</td>
              <td className="px-4 py-3 text-muted-foreground">{closedLabel(s) ?? "—"}</td>
              <td className="px-4 py-3 text-muted-foreground">
                <ChevronRight aria-hidden className="size-4" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SettlementCard({ settlement: s }: { settlement: SettlementSummary }) {
  const name = `${s.month} · ${title(s)}`;
  return (
    <article
      aria-label={name}
      className="relative flex flex-col gap-1.5 rounded-2xl border border-border bg-card shadow-sm px-4 py-3.5 hover:bg-muted"
    >
      <div className="flex items-start gap-2">
        <Link
          to="/mentor/settlements/$settlementId"
          params={{ settlementId: s.id }}
          className={cn("min-w-0 flex-1 text-body-strong text-foreground", STRETCHED)}
        >
          {name}
        </Link>
        <span className="shrink-0 text-body-strong text-foreground">{won(s.total_amount)}</span>
      </div>
      <p className="text-caption text-muted-foreground">
        {[`세션 ${s.session_count}회`, formatMinutes(s.total_minutes), closedLabel(s)].filter(Boolean).join(" · ")}
      </p>
    </article>
  );
}
