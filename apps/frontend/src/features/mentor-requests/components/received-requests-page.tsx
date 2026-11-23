import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronRight, FileText } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LoadMore } from "@/components/load-more";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import type { MentoringRequest } from "@/features/requests/api";
import { cn } from "@/lib/utils";

import {
  cohortOptions,
  myAssignmentsQuery,
  RECEIVED_TABS,
  receivedRequestsQuery,
  receivedTabCount,
  type ReceivedTab,
} from "../api";
import { desiredLabel, metaLabel, RECEIVED_STATUS, requestedAt, requesterLabel } from "../labels";

const ALL_COHORTS = "all";

/** 멘토 받은 신청 목록 (Figma `Column / 받은 신청 · 목록 (FE-9a)`, F43·A76). 데스크톱은 표, 그 밖은 카드 */
export function ReceivedRequestsPage({ tab, cohortId }: { tab: ReceivedTab; cohortId: string | undefined }) {
  const list = useInfiniteQuery(receivedRequestsQuery(tab, cohortId));
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const counts = list.data?.pages[0]?.counts;
  const emptyAll = counts ? receivedTabCount("all", counts) === 0 : false;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">받은 신청</h1>
        <p className="text-body text-muted-foreground">희망 일시 중 하나를 골라 승인하거나 사유와 함께 반려해요.</p>
      </div>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
        <nav aria-label="신청 상태" className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0 lg:flex-1">
          <ul className="flex min-w-max gap-1 border-b border-border">
            {RECEIVED_TABS.map((t) => {
              const active = t.value === tab;
              const count = counts ? receivedTabCount(t.value, counts) : null;
              return (
                <li key={t.value}>
                  <Link
                    to="/mentor/requests"
                    search={{
                      ...(t.value === "pending" ? {} : { tab: t.value }),
                      ...(cohortId ? { cohort: cohortId } : {}),
                    }}
                    aria-current={active ? "page" : undefined}
                    aria-label={count === null ? t.label : `${t.label} ${count}`}
                    className={cn(
                      "-mb-px inline-flex h-10 items-center gap-1.5 border-b-2 px-3 text-body outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      active
                        ? "border-primary text-primary-text"
                        : "border-transparent text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {t.label}
                    {count === null ? null : <span>{count}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <CohortFilter tab={tab} cohortId={cohortId} />
      </div>
      {list.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : list.isError ? (
        <ErrorState onRetry={() => void list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={FileText}
          title={emptyAll ? "아직 받은 신청이 없어요" : "이 상태의 신청이 없어요"}
          description={emptyAll ? "수강생이 멘토링을 신청하면 여기에 모여요." : undefined}
        />
      ) : (
        <>
          <RequestTable items={items} />
          <ul className="flex flex-col gap-2.5 lg:hidden">
            {items.map((r) => (
              <li key={r.id}>
                <RequestCard request={r} />
              </li>
            ))}
          </ul>
        </>
      )}
      {list.hasNextPage ? (
        <LoadMore
          loading={list.isFetchingNextPage}
          label="다음 신청을 불러오는 중…"
          onVisible={() => void list.fetchNextPage()}
        />
      ) : null}
    </div>
  );
}

/** 기수 필터: 내 배정 기수 전체(비활성 포함), 맨 위는 전체 기수 (F43) */
function CohortFilter({ tab, cohortId }: { tab: ReceivedTab; cohortId: string | undefined }) {
  const navigate = useNavigate();
  const assignments = useQuery(myAssignmentsQuery);
  const options = cohortOptions(assignments.data ?? []);
  return (
    <Select
      value={cohortId ?? ALL_COHORTS}
      onValueChange={(value) =>
        void navigate({
          to: "/mentor/requests",
          search: { ...(tab === "pending" ? {} : { tab }), ...(value === ALL_COHORTS ? {} : { cohort: value }) },
        })
      }
    >
      <SelectTrigger aria-label="기수" className="lg:w-45">
        <SelectValue placeholder="전체 기수" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL_COHORTS}>전체 기수</SelectItem>
        {options.map((o) => (
          <SelectItem key={o.id} value={o.id}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function StatusBadge({ request }: { request: MentoringRequest }) {
  const style = RECEIVED_STATUS[request.status];
  return <Badge variant={style.badge}>{style.label}</Badge>;
}

function RequestTable({ items }: { items: MentoringRequest[] }) {
  return (
    <div className="hidden overflow-hidden rounded-xl border border-border bg-card lg:block">
      <table className="w-full text-left">
        <thead className="bg-muted text-caption text-muted-foreground">
          <tr>
            <th scope="col" className="w-32 px-4 py-2.5 font-normal">
              신청일
            </th>
            <th scope="col" className="px-4 py-2.5 font-normal">
              주제
            </th>
            <th scope="col" className="w-40 px-4 py-2.5 font-normal">
              신청자
            </th>
            <th scope="col" className="w-48 px-4 py-2.5 font-normal">
              희망 일시
            </th>
            <th scope="col" className="w-20 px-4 py-2.5 font-normal">
              상태
            </th>
            <th scope="col" className="w-10">
              <span className="sr-only">상세</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id} className="relative border-t border-border hover:bg-muted">
              <td className="px-4 py-3 text-body text-foreground">{requestedAt(r)}</td>
              <td className="px-4 py-3">
                <span className="flex flex-col gap-0.5">
                  <Link
                    to="/mentor/requests/$requestId"
                    params={{ requestId: r.id }}
                    className="w-fit text-body-strong text-foreground outline-none after:absolute after:inset-0 hover:underline focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {r.topic}
                  </Link>
                  <span className="text-caption text-muted-foreground">{metaLabel(r)}</span>
                </span>
              </td>
              <td className="px-4 py-3 text-body text-foreground">{requesterLabel(r)}</td>
              <td className="px-4 py-3 text-body text-foreground">{desiredLabel(r)}</td>
              <td className="px-4 py-3">
                <StatusBadge request={r} />
              </td>
              <td className="pr-4 text-muted-foreground">
                <ChevronRight aria-hidden className="size-4" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RequestCard({ request }: { request: MentoringRequest }) {
  return (
    <Link
      to="/mentor/requests/$requestId"
      params={{ requestId: request.id }}
      aria-label={`${request.topic} · ${RECEIVED_STATUS[request.status].label}`}
      className="flex flex-col gap-1.5 rounded-xl border border-border bg-card px-4 py-3.5 outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="flex items-center gap-2">
        <span className="min-w-0 flex-1 text-body-strong text-foreground">{request.topic}</span>
        <StatusBadge request={request} />
      </div>
      <p className="text-caption text-muted-foreground">
        {requesterLabel(request)} · {metaLabel(request)}
      </p>
      <div className="flex items-center gap-2">
        <span className="min-w-0 flex-1 text-body text-foreground">
          {request.status === "PENDING" ? "희망" : request.status === "APPROVED" ? "확정" : "희망 일시"}{" "}
          {desiredLabel(request)}
        </span>
        <span className="text-caption text-muted-foreground">신청 {requestedAt(request)}</span>
      </div>
    </Link>
  );
}
