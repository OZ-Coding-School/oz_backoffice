import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { CalendarDays, FileText, LayoutGrid, MessageSquare, PencilLine, Video, type LucideIcon } from "lucide-react";
import { useState } from "react";

import { CardTitle } from "@/components/section-card";
import { PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { Me } from "@/features/auth/api";
import { threadsQuery, unreadTotal } from "@/features/chat/api";
import { AcceptingCard } from "@/features/mentor-schedule/components/accepting-card";
import { scheduleQuery } from "@/features/mentor-schedule/api";
import { canEnterMeet, targetLabel } from "@/features/mentor-sessions/labels";
import type { MentoringRequest } from "@/features/requests/api";
import type { MentoringSession } from "@/features/sessions/api";
import { formatKst, formatKstDay } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { isKstToday } from "../api";
import {
  desiredSummary,
  mentorOldestMissingQuery,
  mentorPendingQuery,
  mentorTodayQuery,
  mentorUpcomingQuery,
} from "../mentor-api";

/** 멘토 홈 (Figma `홈 (FE-13)`, F57). 헬프센터 카드는 범위 밖(F15) */
export function MentorHome({ me }: { me: Me }) {
  // 화면을 여는 시각으로 '오늘'을 정한다
  const [now] = useState(() => Date.now());
  const today = useQuery(mentorTodayQuery(now));
  const upcoming = useQuery(mentorUpcomingQuery);
  const pending = useQuery(mentorPendingQuery);
  const threads = useInfiniteQuery(threadsQuery);
  const missingCount = upcoming.data?.view_counts.record_missing;

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <PageHeader icon={LayoutGrid} title={`안녕하세요, ${me.name}님`} description="오늘 확인할 일을 모아 봤어요." />
      <ul aria-label="할 일 요약" className="grid grid-cols-2 gap-2 md:grid-cols-4 md:gap-3">
        <li>
          <Link to="/mentor/requests" className={SUMMARY}>
            <SummaryBody
              icon={FileText}
              label="처리할 신청"
              value={pending.data ? `${pending.data.counts.PENDING}건` : null}
              tone="text-warning-text"
            />
          </Link>
        </li>
        <li>
          <Link to="/mentor/sessions" className={SUMMARY}>
            <SummaryBody
              icon={CalendarDays}
              label="오늘 세션"
              value={today.data ? `${today.data.total}회` : null}
              tone="text-primary-text"
            />
          </Link>
        </li>
        <li>
          <Link to="/mentor/sessions" search={{ tab: "record_missing" }} className={SUMMARY}>
            <SummaryBody
              icon={PencilLine}
              label="기록 미제출"
              value={missingCount === undefined ? null : `${missingCount}회`}
              tone="text-destructive-text"
            />
          </Link>
        </li>
        <li>
          <Link to="/mentoring/chat" className={SUMMARY}>
            <SummaryBody
              icon={MessageSquare}
              label="안 읽은 채팅"
              value={threads.data ? `${unreadTotal(threads.data)}개` : null}
              tone="text-info-text"
            />
          </Link>
        </li>
      </ul>
      {missingCount ? <MissingWarning count={missingCount} /> : null}
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-6">
        <SessionsCard sessions={upcoming.data?.items} now={now} />
        <div className="flex flex-col gap-4 lg:gap-6">
          <RequestsCard requests={pending.data?.items} />
          <Accepting />
        </div>
      </div>
    </div>
  );
}

const SUMMARY =
  "flex h-full flex-col justify-between gap-1.5 rounded-2xl border border-border bg-card shadow-sm p-3 outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring md:gap-2 md:p-4";

function SummaryBody({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: LucideIcon;
  label: string;
  value: string | null;
  tone: string;
}) {
  return (
    <>
      <span className="flex items-center gap-2 text-caption text-muted-foreground">
        <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-lg bg-sidebar-accent text-sidebar-accent-foreground">
          <Icon aria-hidden className="size-3.5" />
        </span>
        {label}
      </span>
      <span className={cn("text-h2", value ? tone : "text-muted-foreground")}>{value ?? "-"}</span>
    </>
  );
}

function when(session: Pick<MentoringSession, "starts_at" | "ends_at">, now: number): string {
  const day = isKstToday(session.starts_at, now) ? "오늘" : formatKstDay(session.starts_at);
  return `${day} ${formatKst(session.starts_at, "HH:mm")}~${formatKst(session.ends_at, "HH:mm")}`;
}

/** 기록 미제출 경고 (F57): 가장 오래된 하나, 여럿이면 [모두 보기] */
function MissingWarning({ count }: { count: number }) {
  const oldest = useQuery(mentorOldestMissingQuery);
  const session = oldest.data?.items[0];
  return (
    <div className="flex flex-col gap-2 md:flex-row md:items-center md:gap-3">
      <Alert
        variant="warning"
        className="md:flex-1"
        title={`기록하지 않은 세션이 ${count}회 있어요`}
        description={
          session
            ? `${formatKstDay(session.starts_at)} ${formatKst(session.starts_at, "HH:mm")} ${session.topic}(${targetLabel(session)}). 기록을 제출해야 정산에 들어가요.`
            : "기록을 제출해야 정산에 들어가요."
        }
      />
      {count > 1 ? (
        <Button asChild variant="outline" className="max-md:w-full">
          <Link to="/mentor/sessions" search={{ tab: "record_missing" }}>
            모두 보기
          </Link>
        </Button>
      ) : session ? (
        <Button asChild variant="outline" className="max-md:w-full">
          <Link to="/mentor/sessions/$sessionId" params={{ sessionId: session.id }}>
            기록 작성
          </Link>
        </Button>
      ) : null}
    </div>
  );
}

const CARD = "flex flex-col gap-3 rounded-2xl border border-border bg-card shadow-sm p-4 md:p-5";
const ITEM = "flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border py-3 last:border-b-0";
const ITEM_LINK =
  "flex min-w-0 flex-1 basis-56 items-center gap-3 rounded-md outline-none hover:opacity-80 focus-visible:ring-2 focus-visible:ring-ring";

function CardHead({
  id,
  title,
  to,
  more,
}: {
  id: string;
  title: string;
  to: "/mentor/sessions" | "/mentor/requests";
  more: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <CardTitle icon={to === "/mentor/sessions" ? Video : FileText} id={id} className="flex-1">
        {title}
      </CardTitle>
      <Link to={to} className="text-body-sm text-primary-text hover:underline">
        {more}
      </Link>
    </div>
  );
}

function SessionsCard({ sessions, now }: { sessions: MentoringSession[] | undefined; now: number }) {
  return (
    <section aria-labelledby="home-sessions" className={CARD}>
      <CardHead id="home-sessions" title="오늘·다가오는 세션" to="/mentor/sessions" more="세션 전체" />
      {!sessions ? (
        <div className="flex justify-center py-6">
          <Spinner />
        </div>
      ) : sessions.length === 0 ? (
        <p className="border-t border-border py-6 text-center text-body text-muted-foreground">
          다가오는 세션이 없어요.
        </p>
      ) : (
        <ul className="flex flex-col border-t border-border">
          {sessions.map((s) => (
            <SessionItem key={s.id} session={s} now={now} />
          ))}
        </ul>
      )}
    </section>
  );
}

function SessionItem({ session, now }: { session: MentoringSession; now: number }) {
  const live = session.status === "IN_PROGRESS";
  const today = isKstToday(session.starts_at, now);
  const badge = live ? (
    <Badge variant="primary">진행 중</Badge>
  ) : today ? (
    <Badge variant="info">오늘</Badge>
  ) : (
    <Badge variant="secondary">예정</Badge>
  );
  return (
    <li className={ITEM}>
      <Link to="/mentor/sessions/$sessionId" params={{ sessionId: session.id }} className={ITEM_LINK}>
        <span
          aria-hidden
          className="flex size-12 shrink-0 flex-col items-center justify-center rounded-lg bg-accent text-caption text-primary-text"
        >
          <span>{formatKst(session.starts_at, "M월")}</span>
          <span className="text-body-strong">{formatKst(session.starts_at, "d")}</span>
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="truncate text-body-strong text-foreground">{session.topic}</span>
          <span className="text-caption text-muted-foreground">
            {targetLabel(session)} · {when(session, now)}
          </span>
        </span>
        {badge}
      </Link>
      {canEnterMeet(session, now) ? (
        <Button asChild size="sm" className="max-md:w-full">
          <a href={session.google_meet_url ?? undefined} target="_blank" rel="noopener noreferrer">
            <Video aria-hidden />
            Meet 입장
          </a>
        </Button>
      ) : null}
    </li>
  );
}

function RequestsCard({ requests }: { requests: MentoringRequest[] | undefined }) {
  return (
    <section aria-labelledby="home-requests" className={CARD}>
      <CardHead id="home-requests" title="처리할 신청" to="/mentor/requests" more="전체" />
      {!requests ? (
        <div className="flex justify-center py-6">
          <Spinner />
        </div>
      ) : requests.length === 0 ? (
        <p className="border-t border-border py-6 text-center text-body text-muted-foreground">처리할 신청이 없어요.</p>
      ) : (
        <ul className="flex flex-col border-t border-border">
          {requests.map((r) => (
            <li key={r.id} className={ITEM}>
              <Link to="/mentor/requests/$requestId" params={{ requestId: r.id }} className={ITEM_LINK}>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="truncate text-body-strong text-foreground">{r.topic}</span>
                  <span className="text-caption text-muted-foreground">
                    {r.team_id ? (r.team_label ?? "팀") : r.requester_name} · {desiredSummary(r)}
                  </span>
                </span>
                <Badge variant="warning">대기</Badge>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Accepting() {
  const schedule = useQuery(scheduleQuery);
  if (!schedule.data) return null;
  return (
    <AcceptingCard
      accepting={schedule.data.accepting_requests}
      description="켜 두면 수강생이 내 가능 시간에 신청할 수 있어요. 끄면 대기 중인 신청은 자동으로 취소돼요."
    />
  );
}
