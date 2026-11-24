import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, FileSearch } from "lucide-react";

import { ApiError } from "@/api/errors";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { formatKstDayTime, formatMinutes } from "@/lib/datetime";

import { mySettlementQuery, type SettlementDetail, type SettlementItem } from "../api";
import { cohortLabel, counterpartLabel, detailSubtitle, itemTypeLabel, monthTitle, unitPrice, won } from "../labels";

/**
 * 멘토 정산서 명세 (Figma `Group / 정산 · 목록·상세 (FE-12a)`, F54·A55·A80).
 * 미차감 초과(A78)는 운영진 참고용이라 보여 주지 않는다
 */
export function SettlementPage({ settlementId }: { settlementId: string }) {
  const detail = useQuery(mySettlementQuery(settlementId));
  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <Link
        to="/mentor/settlements"
        className="inline-flex w-fit items-center gap-1.5 text-body-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft aria-hidden className="size-4" />
        정산
      </Link>
      {detail.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : detail.isError ? (
        detail.error instanceof ApiError && detail.error.status === 404 ? (
          <EmptyState
            icon={FileSearch}
            title="정산서를 찾을 수 없어요"
            description="마감된 내 정산서만 볼 수 있어요. 정산 목록에서 다시 골라 주세요."
          />
        ) : (
          <ErrorState onRetry={() => void detail.refetch()} />
        )
      ) : (
        <Detail settlement={detail.data} />
      )}
    </div>
  );
}

function Detail({ settlement: s }: { settlement: SettlementDetail }) {
  const stats = [
    { label: "세션", value: `${s.session_count}회` },
    { label: "정산 시간", value: formatMinutes(s.total_minutes) },
    { label: "금액", value: won(s.total_amount) },
  ];
  return (
    <>
      <header className="flex items-start gap-3">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <h1 className="text-h1 break-keep text-foreground">
            {[monthTitle(s.month), cohortLabel(s)].filter(Boolean).join(" · ")}
          </h1>
          <p className="text-body text-muted-foreground">{detailSubtitle(s)}</p>
        </div>
        <Badge variant="secondary" className="shrink-0">
          마감
        </Badge>
      </header>
      <dl className="grid gap-2.5 md:grid-cols-3 md:gap-4">
        {stats.map((stat) => (
          <div key={stat.label} className="flex flex-col gap-1 rounded-xl border border-border bg-card p-4 md:p-5">
            <dt className="text-caption text-muted-foreground">{stat.label}</dt>
            <dd className="text-h2 text-foreground">{stat.value}</dd>
          </div>
        ))}
      </dl>
      {s.items.length === 0 ? (
        <EmptyState icon={FileSearch} title="명세 항목이 없어요" />
      ) : (
        <>
          <ItemTable items={s.items} />
          <ul aria-label="명세" className="flex flex-col gap-2.5 lg:hidden">
            {s.items.map((item) => (
              <li key={item.session_id}>
                <ItemCard item={item} />
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function when(item: SettlementItem): string {
  return item.session_starts_at ? formatKstDayTime(item.session_starts_at) : "—";
}

function TypeBadge({ item }: { item: SettlementItem }) {
  const type = itemTypeLabel(item);
  return <Badge variant={type.badge}>{type.label}</Badge>;
}

function ItemTable({ items }: { items: SettlementItem[] }) {
  return (
    <div className="hidden overflow-hidden rounded-xl border border-border bg-card lg:block">
      <table className="w-full text-left">
        <thead className="bg-muted text-caption text-muted-foreground">
          <tr>
            <th scope="col" className="w-40 px-4 py-2.5 font-normal">
              일시
            </th>
            <th scope="col" className="px-4 py-2.5 font-normal">
              세션
            </th>
            <th scope="col" className="w-24 px-4 py-2.5 font-normal">
              유형
            </th>
            <th scope="col" className="w-28 px-4 py-2.5 text-right font-normal">
              정산 시간
            </th>
            <th scope="col" className="w-36 px-4 py-2.5 text-right font-normal">
              단가
            </th>
            <th scope="col" className="w-32 px-4 py-2.5 text-right font-normal">
              금액
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.session_id} className="border-t border-border text-body">
              <td className="px-4 py-3 text-foreground">{when(item)}</td>
              <td className="px-4 py-3">
                <span className="flex flex-col gap-0.5">
                  <span className="text-body-strong text-foreground">{counterpartLabel(item)}</span>
                  {item.session_topic ? (
                    <span className="text-caption text-muted-foreground">{item.session_topic}</span>
                  ) : null}
                </span>
              </td>
              <td className="px-4 py-3">
                <TypeBadge item={item} />
              </td>
              <td className="px-4 py-3 text-right text-foreground">{item.billable_minutes}분</td>
              <td className="px-4 py-3 text-right text-foreground">{unitPrice(item)}</td>
              <td className="px-4 py-3 text-right text-foreground">{won(item.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ItemCard({ item }: { item: SettlementItem }) {
  return (
    <article
      aria-label={`${when(item)} ${counterpartLabel(item)}`}
      className="flex flex-col gap-1.5 rounded-xl border border-border bg-card px-4 py-3.5"
    >
      <div className="flex items-center gap-2">
        <span className="flex-1 text-body-strong text-foreground">{when(item)}</span>
        <TypeBadge item={item} />
      </div>
      <p className="text-caption text-muted-foreground">
        {[counterpartLabel(item), item.session_topic].filter(Boolean).join(" · ")}
      </p>
      <div className="flex items-center gap-2 text-body">
        <span className="flex-1 text-foreground">
          {item.billable_minutes}분 · {unitPrice(item)}
        </span>
        <span className="text-body-strong text-foreground">{won(item.amount)}</span>
      </div>
    </article>
  );
}
