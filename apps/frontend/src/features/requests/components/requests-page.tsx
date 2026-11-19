import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { FileText } from "lucide-react";
import { useEffect, useEffectEvent, useMemo, useRef } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Spinner } from "@/components/ui/spinner";
import { enrollmentsQuery } from "@/features/member/api";
import { cn } from "@/lib/utils";

import { myRequestsQuery, REQUEST_TABS, tabCount, type RequestTab } from "../api";
import { RequestCard } from "./request-card";

/** 수강생 신청 내역 (Figma `Column / 신청 내역 (FE-4a)`, F29·A67). 탭은 검색 파라미터 `tab`. */
export function RequestsPage({ tab }: { tab: RequestTab }) {
  const list = useInfiniteQuery(myRequestsQuery(tab));
  const enrollments = useQuery(enrollmentsQuery);
  const myStudentIds = useMemo(() => new Set((enrollments.data ?? []).map((e) => e.student_id)), [enrollments.data]);
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const counts = list.data?.pages[0]?.counts;
  const emptyAll = counts ? tabCount("all", counts) === 0 : false;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">신청 내역</h1>
        <p className="text-body text-muted-foreground">
          보낸 멘토링 신청과 처리 결과예요. 승인되면 진행 기록에 세션이 생겨요.
        </p>
      </div>
      <nav aria-label="신청 상태" className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
        <ul className="flex min-w-max gap-1 border-b border-border">
          {REQUEST_TABS.map((t) => {
            const active = t.value === tab;
            return (
              <li key={t.value}>
                <Link
                  to="/mentoring/requests"
                  search={t.value === "all" ? {} : { tab: t.value }}
                  aria-current={active ? "page" : undefined}
                  aria-label={counts ? `${t.label} ${tabCount(t.value, counts)}` : t.label}
                  className={cn(
                    "-mb-px inline-flex h-10 items-center gap-1.5 border-b-2 px-3 text-body outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    active
                      ? "border-primary text-primary-text"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t.label}
                  {counts ? <span>{tabCount(t.value, counts)}</span> : null}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      {list.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : list.isError ? (
        <ErrorState onRetry={() => void list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={FileText}
          title={emptyAll ? "아직 보낸 신청이 없어요" : "이 상태의 신청이 없어요"}
          description={emptyAll ? "멘토링을 신청하면 여기에서 처리 결과를 볼 수 있어요." : undefined}
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {items.map((r) => (
            <li key={r.id}>
              <RequestCard request={r} mine={myStudentIds.has(r.requester_id)} />
            </li>
          ))}
        </ul>
      )}
      {list.hasNextPage ? (
        <LoadMore loading={list.isFetchingNextPage} onVisible={() => void list.fetchNextPage()} />
      ) : null}
    </div>
  );
}

/** 무한 스크롤 (F29): 목록 끝이 화면에 들어오면 다음 20개를 불러온다 */
function LoadMore({ loading, onVisible }: { loading: boolean; onVisible: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const visible = useEffectEvent(onVisible);
  // 불러온 뒤에도 끝이 보이면 다시 관찰을 시작해 바로 다음 묶음을 부른다
  useEffect(() => {
    const el = ref.current;
    if (loading || !el || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) visible();
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [loading]);
  return (
    <div ref={ref} className="flex justify-center py-2 text-body-sm text-muted-foreground">
      {loading ? "다음 신청을 불러오는 중…" : ""}
    </div>
  );
}
