import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, CalendarDays, FileSearch, Timer, User, Users, Video } from "lucide-react";
import { useMemo } from "react";

import { ApiError } from "@/api/errors";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Markdown } from "@/components/markdown";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { enrollmentsQuery } from "@/features/member/api";
import { formatKst } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { sessionQuery, type MentoringSession } from "../api";
import { actualMinutes, balanceNote, isMine, kindLabel, plannedMinutes, scheduleLabel, STATUS_STYLE } from "../labels";
import { ParticipantChips, SessionNote } from "./session-card";

/**
 * 세션 상세 (Figma `Screen / 세션 상세 · 완료 / 예정`, F33·F34).
 * 신청 내용은 신청 상세에서 보므로 머리에 [신청 보기]를 둔다. 다시 보기는 FE-5b.
 */
export function SessionDetailPage({ sessionId }: { sessionId: string }) {
  const detail = useQuery(sessionQuery(sessionId));
  return (
    <div className="flex flex-col gap-6">
      <Link
        to="/mentoring/sessions"
        className="inline-flex w-fit items-center gap-1.5 text-body-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft aria-hidden className="size-4" />
        진행 기록
      </Link>
      {detail.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : detail.isError ? (
        detail.error instanceof ApiError && detail.error.status === 404 ? (
          <EmptyState
            icon={FileSearch}
            title="세션을 찾을 수 없어요"
            description="삭제됐거나 볼 수 없는 세션이에요. 진행 기록에서 다시 골라 주세요."
          />
        ) : (
          <ErrorState onRetry={() => void detail.refetch()} />
        )
      ) : (
        <Detail session={detail.data} />
      )}
    </div>
  );
}

function Detail({ session }: { session: MentoringSession }) {
  const enrollments = useQuery(enrollmentsQuery);
  const myStudentIds = useMemo(() => new Set((enrollments.data ?? []).map((e) => e.student_id)), [enrollments.data]);
  const style = STATUS_STYLE[session.status];
  const KindIcon = session.team_id ? Users : User;
  const upcoming = session.status === "SCHEDULED" || session.status === "IN_PROGRESS";
  const completed = session.status === "COMPLETED";
  const actual = actualMinutes(session);
  const note = balanceNote(session);

  return (
    <div className="flex flex-col gap-4 lg:gap-6">
      <article className="flex min-w-0 flex-col overflow-hidden rounded-xl border border-border bg-card">
        <header className={cn("flex flex-col gap-4 px-4 py-6 md:px-7", style.card)}>
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-background px-2 py-0.5 text-caption-strong text-accent-foreground">
                <KindIcon aria-hidden className="size-3.5" />
                {kindLabel(session)}
              </span>
              <Badge variant={style.badge}>{style.label}</Badge>
            </div>
            <h1 className="text-display text-foreground">{session.title}</h1>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
              <div className="flex min-w-0 items-center gap-2">
                <span className="text-caption text-muted-foreground">멘토</span>
                <Avatar name={session.mentor_display_name} size="sm" />
                <span className="text-body-strong text-foreground">{session.mentor_display_name}</span>
                {session.mentor_headline ? (
                  <span className="truncate text-caption text-muted-foreground">{session.mentor_headline}</span>
                ) : null}
              </div>
              <div className="flex min-w-0 items-center gap-2">
                <span className="text-caption text-muted-foreground">참여자</span>
                <ParticipantChips session={session} myStudentIds={myStudentIds} />
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 lg:flex lg:justify-end">
            {upcoming && session.google_meet_url ? (
              <Button asChild>
                <a href={session.google_meet_url} target="_blank" rel="noopener noreferrer">
                  <Video aria-hidden />
                  Meet 입장
                </a>
              </Button>
            ) : null}
            <Button
              asChild
              variant="outline"
              className={cn(!(upcoming && session.google_meet_url) && "col-span-2 lg:col-span-1")}
            >
              <Link to="/mentoring/requests/$requestId" params={{ requestId: session.request_id }}>
                신청 보기
              </Link>
            </Button>
          </div>
        </header>
        <dl
          className={cn(
            "grid grid-cols-1 divide-y divide-border border-t border-border md:divide-x md:divide-y-0",
            completed ? "md:grid-cols-3" : "md:grid-cols-2",
          )}
        >
          <Fact
            icon={CalendarDays}
            label="예약 일시"
            value={scheduleLabel(session)}
            sub={`신청 ${plannedMinutes(session)}분`}
          />
          {completed ? (
            <Fact
              icon={Video}
              label="실제 진행"
              mono
              value={
                session.actual_started_at && session.actual_ended_at
                  ? `${formatKst(session.actual_started_at, "HH:mm")} ~ ${formatKst(session.actual_ended_at, "HH:mm")}`
                  : "-"
              }
              sub={actual === null ? "Meet 기록 없음" : `Meet 기록 ${actual}분`}
            />
          ) : null}
          <Fact
            icon={Timer}
            label="진행 시간"
            value={`${completed && session.record_duration_minutes !== null ? session.record_duration_minutes : plannedMinutes(session)}분`}
            sub={note}
          />
        </dl>
        {session.status === "NO_SHOW" || session.status === "CANCELED" ? (
          <div className="px-4 py-5 md:px-7">
            <SessionNote session={session} mine={isMine(session, myStudentIds)} />
          </div>
        ) : null}
      </article>
      {completed && session.recorded_at ? <MentorRecord session={session} recordedAt={session.recorded_at} /> : null}
    </div>
  );
}

function Fact({
  icon: Icon,
  label,
  value,
  sub,
  mono = false,
}: {
  icon: typeof Timer;
  label: string;
  value: string;
  sub: string | null;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 px-4 py-3.5 md:px-7">
      <dt className="inline-flex items-center gap-1.5 text-caption text-muted-foreground">
        <Icon aria-hidden className="size-3.5" />
        {label}
      </dt>
      <dd className={cn("text-body-strong text-foreground", mono && "font-mono")}>{value}</dd>
      {sub ? <dd className="text-caption text-muted-foreground">{sub}</dd> : null}
    </div>
  );
}

/** 멘토 기록 (A53): 기록이 있을 때만 전체 폭 (F34) */
function MentorRecord({ session, recordedAt }: { session: MentoringSession; recordedAt: string }) {
  return (
    <section aria-labelledby="mentor-record" className="flex flex-col rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-4 md:px-5">
        <h2 id="mentor-record" className="text-h3 text-foreground">
          멘토 기록
        </h2>
        <span className="text-caption text-muted-foreground">{formatKst(recordedAt, "MM/dd HH:mm")} 제출</span>
      </div>
      <div className="flex flex-col gap-1.5 border-b border-border px-4 py-4 md:px-5">
        <span className="text-caption text-muted-foreground">멘토링 주제</span>
        <p className="text-body-lg text-foreground">{session.topic}</p>
      </div>
      <div className="flex flex-col gap-2 px-4 py-4 md:px-5">
        <span className="text-caption text-muted-foreground">요약</span>
        {session.summary ? (
          <div className="rounded-lg border border-border bg-muted px-4 py-4">
            <Markdown>{session.summary}</Markdown>
          </div>
        ) : null}
      </div>
    </section>
  );
}
