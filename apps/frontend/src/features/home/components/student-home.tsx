import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { CalendarDays, Hourglass, LayoutGrid, MessageSquare, Video, type LucideIcon } from "lucide-react";
import { useState } from "react";

import { CardTitle } from "@/components/section-card";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { Me } from "@/features/auth/api";
import { threadsQuery, unreadTotal } from "@/features/chat/api";
import { activeCohort, enrollmentsQuery } from "@/features/member/api";
import {
  balancesQuery,
  mentoringSettingsQuery,
  type BalanceAccount,
  type MentoringRequest,
} from "@/features/requests/api";
import type { MentoringSession } from "@/features/sessions/api";
import { formatKst, formatKstDay, formatMinutes } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { isKstToday, pendingRequestsQuery, todaySessionsQuery, upcomingSessionsQuery } from "../api";

/** 수강생 홈 (Figma `Column / 홈 (FE-8)`, F42). 신청서·서류·헬프센터·내 문서함은 범위 밖(F15) */
export function StudentHome({ me }: { me: Me }) {
  // 화면을 여는 시각으로 '오늘'을 정한다 (자정을 넘겨 열어 두면 다시 들어와야 바뀐다)
  const [now] = useState(() => Date.now());
  const today = useQuery(todaySessionsQuery(now));
  const pending = useQuery(pendingRequestsQuery);
  const threads = useInfiniteQuery(threadsQuery);
  const canApply = useCanApply();

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <PageHeader icon={LayoutGrid} title={`안녕하세요, ${me.name}님`} description="오늘 확인할 일을 모아 봤어요." />
      <ul aria-label="할 일 요약" className="grid grid-cols-3 gap-2 md:gap-3">
        <li>
          <Link to="/mentoring/sessions" search={{ tab: "scheduled" }} className={SUMMARY}>
            <SummaryBody
              icon={CalendarDays}
              label="오늘 멘토링"
              value={today.data ? `${today.data.total}회` : null}
              tone="text-primary-text"
            />
          </Link>
        </li>
        <li>
          <Link to="/mentoring/requests" search={{ tab: "pending" }} className={SUMMARY}>
            <SummaryBody
              icon={Hourglass}
              label="승인 대기 신청"
              value={pending.data ? `${pending.data.total}건` : null}
              tone="text-warning-text"
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
      <MentoringCard now={now} canApply={canApply} pending={pending.data?.items} />
    </div>
  );
}

/** 수강 중이고 기수가 1:1이나 팀을 허용할 때 [멘토링 신청] (F31·F42). 수강이 끝났으면 숨긴다 */
function useCanApply(): boolean {
  const enrollments = useQuery(enrollmentsQuery);
  const cohort = enrollments.data ? activeCohort(enrollments.data) : null;
  const settings = useQuery({
    ...mentoringSettingsQuery(cohort?.enrollment.cohort_id ?? ""),
    enabled: !!cohort && !cohort.readOnly,
  });
  return (
    !!cohort &&
    !cohort.readOnly &&
    !!settings.data &&
    (settings.data.allow_1_on_1 || settings.data.allow_team_mentoring)
  );
}

const SUMMARY =
  "flex h-full flex-col justify-between gap-1.5 rounded-2xl border border-border bg-card shadow-sm p-3 outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring md:gap-2 md:p-4";

/** 요약 칸: 아이콘·이름(휴대폰은 두 줄로 넘김)과 수. 불러오기 전은 '-' */
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

function MentoringCard({
  now,
  canApply,
  pending,
}: {
  now: number;
  canApply: boolean;
  pending: MentoringRequest[] | undefined;
}) {
  const upcoming = useQuery(upcomingSessionsQuery);
  const sessions = upcoming.data?.items ?? [];
  const requests = pending ?? [];
  const loading = upcoming.isPending || !pending;
  return (
    <section
      aria-labelledby="home-mentoring"
      className="flex flex-col gap-4 rounded-2xl border border-border bg-card shadow-sm p-4 md:p-5"
    >
      <div className="flex items-center gap-2">
        <CardTitle icon={Video} id="home-mentoring" className="flex-1">
          멘토링
        </CardTitle>
        {canApply ? (
          <Link to="/mentoring/apply" className="text-body-sm text-primary-text hover:underline">
            멘토링 신청
          </Link>
        ) : null}
      </div>
      <Balances />
      {loading ? (
        <div className="flex justify-center py-6">
          <Spinner />
        </div>
      ) : sessions.length === 0 && requests.length === 0 ? (
        <div className="flex flex-col items-center gap-1.5 py-6 text-center">
          <p className="text-body-strong text-foreground">예정된 멘토링이 없어요</p>
          <p className="text-body-sm text-muted-foreground">멘토에게 1:1 또는 팀 멘토링을 신청해 보세요.</p>
          {canApply ? (
            <Button asChild size="sm" className="mt-2">
              <Link to="/mentoring/apply">멘토링 신청</Link>
            </Button>
          ) : null}
        </div>
      ) : (
        <ul className="flex flex-col border-t border-border">
          {sessions.map((s) => (
            <SessionItem key={s.id} session={s} now={now} />
          ))}
          {requests.map((r) => (
            <RequestItem key={r.id} request={r} />
          ))}
        </ul>
      )}
    </section>
  );
}

/** 남은 시간: 만료되지 않은 1:1 계좌와 팀 계좌 */
function Balances() {
  const balances = useQuery(balancesQuery);
  const live = (balances.data ?? []).filter((a) => !a.is_expired);
  const solo = live.find((a) => a.owner_type === "STUDENT");
  const team = live.find((a) => a.owner_type === "TEAM");
  return (
    <div className="grid grid-cols-1 gap-2 md:grid-cols-2 md:gap-3">
      <BalanceCell
        label="1:1 남은 시간"
        account={solo}
        note={solo && solo.held_minutes > 0 ? `차감 예정 ${formatMinutes(solo.held_minutes)}` : null}
      />
      {team ? <BalanceCell label="팀 남은 시간" account={team} note={team.owner_name} /> : null}
    </div>
  );
}

function BalanceCell({ label, account, note }: { label: string; account?: BalanceAccount; note: string | null }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg bg-muted px-3.5 py-3">
      <span className="text-caption text-muted-foreground">{label}</span>
      <span className="flex items-baseline gap-2">
        <span className="text-h2 text-foreground">{account ? formatMinutes(account.remaining_minutes) : "-"}</span>
        <span className="text-caption text-muted-foreground">{account ? note : "아직 지급된 시간이 없어요"}</span>
      </span>
    </div>
  );
}

const ITEM = "flex flex-col gap-2.5 border-b border-border py-3 last:border-b-0 md:flex-row md:items-center md:gap-3";
const ITEM_LINK =
  "flex min-w-0 flex-1 items-center gap-3 rounded-md outline-none hover:opacity-80 focus-visible:ring-2 focus-visible:ring-ring";

function SessionItem({ session, now }: { session: MentoringSession; now: number }) {
  const today = isKstToday(session.starts_at, now);
  const live = session.status === "IN_PROGRESS";
  const kind = session.team_id ? (session.team_label ?? "팀") : "1:1";
  const day = today ? "오늘" : formatKstDay(session.starts_at);
  const time = `${formatKst(session.starts_at, "HH:mm")}~${formatKst(session.ends_at, "HH:mm")}`;
  const badge = live ? (
    <Badge variant="primary">진행 중</Badge>
  ) : today ? (
    <Badge variant="info">오늘</Badge>
  ) : (
    <Badge variant="secondary">예정</Badge>
  );
  return (
    <li className={ITEM}>
      <Link to="/mentoring/sessions/$sessionId" params={{ sessionId: session.id }} className={ITEM_LINK}>
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
            {session.mentor_display_name} · {kind} · {day} {time}
          </span>
        </span>
        {badge}
      </Link>
      {(today || live) && session.google_meet_url ? (
        <Button asChild size="sm" className="h-10 md:h-8">
          <a href={session.google_meet_url} target="_blank" rel="noopener noreferrer">
            <Video aria-hidden />
            Meet 입장
          </a>
        </Button>
      ) : null}
    </li>
  );
}

function RequestItem({ request }: { request: MentoringRequest }) {
  return (
    <li className={ITEM}>
      <Link to="/mentoring/requests/$requestId" params={{ requestId: request.id }} className={ITEM_LINK}>
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="truncate text-body-strong text-foreground">{request.topic}</span>
          <span className="text-caption text-muted-foreground">
            {request.mentor_display_name} · 희망 일시 {request.desired_times.length}개 · 승인 대기
          </span>
        </span>
        <Badge variant="warning">대기</Badge>
      </Link>
    </li>
  );
}
