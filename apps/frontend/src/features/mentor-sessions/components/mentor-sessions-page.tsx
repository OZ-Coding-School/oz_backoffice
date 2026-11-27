import { useInfiniteQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { CalendarDays, Pencil, Video } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LoadMore } from "@/components/load-more";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { CohortSelect } from "@/features/mentor-requests/components/cohort-select";
import type { MentoringSession } from "@/features/sessions/api";
import { cn } from "@/lib/utils";

import { MENTOR_SESSION_TABS, mentorSessionsQuery, type MentorSessionTab } from "../api";
import { canEnterMeet, durationLabel, mentorStatus, recordState, targetLabel, whenLabel } from "../labels";

/** 멘토 세션 목록 (Figma `Column / 세션 · 목록 (FE-10a)`, F46·F47·A77). 데스크톱은 표, 그 밖은 카드 */
export function MentorSessionsPage({ tab, cohortId }: { tab: MentorSessionTab; cohortId: string | undefined }) {
  const list = useInfiniteQuery(mentorSessionsQuery(tab, cohortId));
  const navigate = useNavigate();
  // 화면을 연 시각으로 오늘·진행됨·미제출을 나눈다
  const [now] = useState(() => Date.now());
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const counts = list.data?.pages[0]?.view_counts;
  const emptyAll = counts ? counts.all === 0 : false;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">세션</h1>
        <p className="text-body text-muted-foreground">예정된 세션과 지난 세션, 기록 제출 상태를 함께 보여 줘요.</p>
      </div>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
        <nav aria-label="세션 구분" className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0 lg:flex-1">
          <ul className="flex min-w-max gap-1 border-b border-border">
            {MENTOR_SESSION_TABS.map((t) => {
              const active = t.value === tab;
              const count = counts ? counts[t.value] : null;
              return (
                <li key={t.value}>
                  <Link
                    to="/mentor/sessions"
                    search={{
                      ...(t.value === "upcoming" ? {} : { tab: t.value }),
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
        <CohortSelect
          value={cohortId}
          onChange={(cohort) =>
            void navigate({
              to: "/mentor/sessions",
              search: { ...(tab === "upcoming" ? {} : { tab }), ...(cohort ? { cohort } : {}) },
            })
          }
        />
      </div>
      {list.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : list.isError ? (
        <ErrorState onRetry={() => void list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={CalendarDays}
          title={emptyAll ? "아직 세션이 없어요" : "이 구분의 세션이 없어요"}
          description={emptyAll ? "신청을 승인하면 세션이 만들어져요." : undefined}
        />
      ) : (
        <>
          <SessionTable items={items} now={now} />
          <ul className="flex flex-col gap-2.5 lg:hidden">
            {items.map((s) => (
              <li key={s.id}>
                <SessionCard session={s} now={now} />
              </li>
            ))}
          </ul>
        </>
      )}
      {list.hasNextPage ? (
        <LoadMore
          loading={list.isFetchingNextPage}
          label="다음 세션을 불러오는 중…"
          onVisible={() => void list.fetchNextPage()}
        />
      ) : null}
    </div>
  );
}

function StatusBadge({ session, now }: { session: MentoringSession; now: number }) {
  const style = mentorStatus(session, now);
  return <Badge variant={style.badge}>{style.label}</Badge>;
}

function RecordCell({ session, now, prefix }: { session: MentoringSession; now: number; prefix?: string }) {
  const record = recordState(session, now);
  if (record.kind === "missing") return <Badge variant="destructive">미제출</Badge>;
  return (
    <span>
      {prefix}
      {record.kind === "submitted" ? record.label : "—"}
    </span>
  );
}

/** 행·카드 동작: 오늘·진행 중이면 Meet 입장, 기록 미제출이면 기록 작성 (F47·F48) */
function Action({ session, now, className }: { session: MentoringSession; now: number; className?: string }) {
  if (canEnterMeet(session, now)) return <MeetButton session={session} className={className} />;
  if (recordState(session, now).kind !== "missing") return null;
  return (
    <Button asChild size="sm" variant="outline" className={cn("relative", className)}>
      <Link to="/mentor/sessions/$sessionId" params={{ sessionId: session.id }}>
        <Pencil aria-hidden />
        기록 작성
      </Link>
    </Button>
  );
}

function hasAction(session: MentoringSession, now: number): boolean {
  return canEnterMeet(session, now) || recordState(session, now).kind === "missing";
}

/** 제목 링크의 누름 영역을 행·카드 전체로 넓힌다 (동작 버튼은 relative로 위에 둔다) */
const STRETCHED = "outline-none after:absolute after:inset-0 after:rounded-xl focus-visible:underline hover:underline";

function MeetButton({ session, className }: { session: MentoringSession; className?: string }) {
  return (
    <Button asChild size="sm" className={cn("relative", className)}>
      <a href={session.google_meet_url ?? undefined} target="_blank" rel="noopener noreferrer">
        <Video aria-hidden />
        Meet 입장
      </a>
    </Button>
  );
}

function SessionTable({ items, now }: { items: MentoringSession[]; now: number }) {
  return (
    <div className="hidden overflow-hidden rounded-2xl border border-border bg-card shadow-sm lg:block">
      <table className="w-full text-left">
        <thead className="bg-muted text-caption text-muted-foreground">
          <tr>
            <th scope="col" className="w-40 px-4 py-2.5 font-normal">
              일시
            </th>
            <th scope="col" className="px-4 py-2.5 font-normal">
              세션
            </th>
            <th scope="col" className="w-40 px-4 py-2.5 font-normal">
              대상
            </th>
            <th scope="col" className="w-24 px-4 py-2.5 font-normal">
              상태
            </th>
            <th scope="col" className="w-28 px-4 py-2.5 font-normal">
              기록
            </th>
            <th scope="col" className="w-32 px-4 py-2.5">
              <span className="sr-only">동작</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.id} className="relative border-t border-border hover:bg-muted">
              <td className="px-4 py-3">
                <span className="flex flex-col gap-0.5">
                  <span className="text-body text-foreground">{whenLabel(s)}</span>
                  <span className="text-caption text-muted-foreground">{durationLabel(s)}</span>
                </span>
              </td>
              <td className="px-4 py-3">
                <span className="flex flex-col gap-0.5">
                  <Link
                    to="/mentor/sessions/$sessionId"
                    params={{ sessionId: s.id }}
                    className={cn("w-fit text-body-strong text-foreground", STRETCHED)}
                  >
                    {s.title}
                  </Link>
                  <span className="text-caption text-muted-foreground">{s.topic}</span>
                </span>
              </td>
              <td className="px-4 py-3 text-body text-foreground">{targetLabel(s)}</td>
              <td className="px-4 py-3">
                <StatusBadge session={s} now={now} />
              </td>
              <td className="px-4 py-3 text-body text-foreground">
                <RecordCell session={s} now={now} />
              </td>
              <td className="px-4 py-3 text-right">
                <Action session={s} now={now} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SessionCard({ session, now }: { session: MentoringSession; now: number }) {
  const action = hasAction(session, now);
  return (
    <article
      aria-label={session.title}
      className="relative flex flex-col gap-1.5 rounded-2xl border border-border bg-card shadow-sm px-4 py-3.5 hover:bg-muted"
    >
      <div className="flex items-center gap-2">
        <h2 className="min-w-0 flex-1 text-body-strong text-foreground">
          <Link to="/mentor/sessions/$sessionId" params={{ sessionId: session.id }} className={STRETCHED}>
            {session.title}
          </Link>
        </h2>
        <StatusBadge session={session} now={now} />
      </div>
      <p className="text-caption text-muted-foreground">
        {targetLabel(session)} · {session.topic}
      </p>
      <div className="flex items-center gap-2">
        <span className="min-w-0 flex-1 text-body text-foreground">
          {whenLabel(session)} · {durationLabel(session)}
        </span>
        <span className="text-caption text-muted-foreground">
          <RecordCell session={session} now={now} prefix="기록 " />
        </span>
        {action ? <Action session={session} now={now} className="max-md:hidden" /> : null}
      </div>
      {action ? <Action session={session} now={now} className="mt-1 h-10 md:hidden" /> : null}
    </article>
  );
}
