import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { CalendarDays, ChevronRight, CircleCheck, Hourglass, MessageSquare, Plus, Users, Wallet } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { expertiseChips, myTeamsQuery, type StudentTeam } from "@/features/apply/api";
import { Chips } from "@/features/apply/components/mentor-step";
import { findThread, threadsQuery } from "@/features/chat/api";
import { MentorDialog } from "@/features/apply/components/mentor-dialog";
import { activeCohort, cohortLabel, ENROLLMENT_STATUS_LABELS, enrollmentsQuery } from "@/features/member/api";
import { balancesQuery } from "@/features/requests/api";
import { teamSessionsQuery } from "@/features/sessions/api";
import { STATUS_STYLE } from "@/features/sessions/labels";
import { formatKst, formatKstDayTime, formatMinutes } from "@/lib/datetime";

/** 내 팀 (Figma `Column / 내 팀 (FE-6c)`, F39·A73) */
export function TeamPage() {
  const teams = useQuery(myTeamsQuery);
  const enrollments = useQuery(enrollmentsQuery);
  const cohort = enrollments.data ? activeCohort(enrollments.data) : null;
  // 활성 기수의 팀을 먼저 고른다 (KDT는 동시 수강이 없어 보통 하나다)
  const team =
    teams.data?.as_student.find((t) => t.cohort_id === cohort?.enrollment.cohort_id) ?? teams.data?.as_student[0];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <div className="flex flex-1 items-center gap-3">
          <span aria-hidden className="inline-flex size-8 items-center justify-center rounded-md bg-accent">
            <Users className="size-4 text-primary-text" />
          </span>
          <div className="flex flex-col">
            <h1 className="text-h2 text-foreground">내 팀</h1>
            <p className="text-caption text-muted-foreground">팀 멘토링을 함께 받는 팀이에요</p>
          </div>
        </div>
        {team ? <TeamChatButton team={team} /> : null}
        {team && cohort && !cohort.readOnly ? (
          <Button asChild size="sm" className="h-10 md:h-8">
            <Link to="/mentoring/apply" search={{ kind: "team" }}>
              <Plus aria-hidden />팀 멘토링 신청
            </Link>
          </Button>
        ) : null}
      </div>
      {teams.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : teams.isError ? (
        <ErrorState onRetry={() => void teams.refetch()} />
      ) : !team ? (
        <EmptyState icon={Users} title="아직 팀에 속해 있지 않아요" description="팀은 운영진이 구성해요." />
      ) : (
        <TeamCard team={team} cohortName={cohort ? cohortLabel(cohort.enrollment) : null} />
      )}
    </div>
  );
}

function TeamCard({ team, cohortName }: { team: StudentTeam; cohortName: string | null }) {
  const enrollments = useQuery(enrollmentsQuery);
  const myStudentIds = useMemo(() => new Set((enrollments.data ?? []).map((e) => e.student_id)), [enrollments.data]);
  const balances = useQuery(balancesQuery);
  const account = balances.data?.find((a) => a.owner_type === "TEAM" && a.owner_id === team.id);
  const [mentorOpen, setMentorOpen] = useState(false);
  const { stats } = team;
  const meta = [
    cohortName,
    `팀원 ${team.members.length}명`,
    team.created_at ? `${formatKst(team.created_at, "MM/dd")} 구성` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  const pendingNote = stats.pending_requester_name
    ? `${stats.pending_requester_name} 신청${stats.pending_requests > 1 ? ` 외 ${stats.pending_requests - 1}건` : ""}`
    : "대기 중인 신청이 없어요";

  return (
    <section aria-label={team.label} className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
      <div className="flex items-center gap-4 bg-accent px-4 py-6 md:px-6">
        <span className="inline-flex size-14 shrink-0 items-center justify-center rounded-xl bg-primary text-body-strong text-primary-foreground">
          {team.team_number}팀
        </span>
        <div className="flex min-w-0 flex-col gap-1">
          <h2 className="text-h1 text-foreground">{team.label}</h2>
          <p className="text-body text-muted-foreground">{meta}</p>
        </div>
      </div>
      <dl className="grid grid-cols-2 border-t border-border lg:grid-cols-4 [&>div]:border-border [&>div:nth-child(even)]:border-l [&>div:nth-child(n+3)]:border-t lg:[&>div]:border-l lg:[&>div:first-child]:border-l-0 lg:[&>div:nth-child(n+3)]:border-t-0">
        <Stat
          icon={Wallet}
          label="팀 남은 시간"
          value={account ? formatMinutes(account.remaining_minutes) : "-"}
          note={
            account
              ? `${account.valid_until.slice(5).replace("-", "/")}까지 · 총 ${formatMinutes(account.total_minutes)} 중`
              : "아직 지급된 시간이 없어요"
          }
        />
        <Stat
          icon={CircleCheck}
          label="진행한 팀 세션"
          value={`${stats.completed_sessions}회`}
          note={`총 ${formatMinutes(stats.completed_minutes)}`}
        />
        <Stat
          icon={CalendarDays}
          label="예정된 팀 세션"
          value={`${stats.upcoming_sessions}회`}
          note={stats.next_session_at ? formatKstDayTime(stats.next_session_at) : "예정된 세션이 없어요"}
        />
        <Stat icon={Hourglass} label="승인 대기 신청" value={`${stats.pending_requests}건`} note={pendingNote} />
      </dl>
      <div className="grid grid-cols-1 border-t border-border lg:grid-cols-[22.5rem_minmax(0,1fr)]">
        <div className="flex flex-col gap-3 px-4 py-5 md:px-6">
          <p className="text-caption text-muted-foreground">담당 멘토</p>
          <div className="flex items-center gap-3">
            <Avatar name={team.mentor.display_name} />
            <div className="flex min-w-0 flex-col">
              <span className="text-body-strong text-foreground">{team.mentor.display_name}</span>
              {team.mentor.headline ? (
                <span className="text-caption text-muted-foreground">{team.mentor.headline}</span>
              ) : null}
            </div>
          </div>
          {team.mentor.expertise ? <Chips items={expertiseChips(team.mentor.expertise)} /> : null}
          {team.mentor.accepting_requests ? (
            <Badge variant="success" className="w-fit">
              신청 받는 중
            </Badge>
          ) : null}
          <Button variant="link" size="sm" className="w-fit" onClick={() => setMentorOpen(true)}>
            상세 소개 보기
          </Button>
        </div>
        <div className="flex flex-col border-t border-border py-5 lg:border-t-0 lg:border-l">
          <p className="px-4 pb-2 text-caption text-muted-foreground md:px-6">팀원 {team.members.length}명</p>
          <ul>
            {team.members.map((m) => {
              const mine = myStudentIds.has(m.student_id);
              return (
                <li
                  key={m.student_id}
                  className={`flex items-center gap-3 px-4 py-2.5 md:px-6 ${mine ? "bg-muted" : ""}`}
                >
                  <Avatar name={m.name} size="sm" />
                  <div className="flex min-w-0 flex-col">
                    <span className="flex items-center gap-1.5 text-body-strong text-foreground">
                      {m.name}
                      {mine ? <Badge variant="outline">나</Badge> : null}
                    </span>
                    {m.status ? (
                      <span className="text-caption text-muted-foreground">{ENROLLMENT_STATUS_LABELS[m.status]}</span>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
      <RecentSessions teamId={team.id} />
      <MentorDialog
        cohortId={team.cohort_id}
        mentorId={mentorOpen ? team.mentor.mentor_id : null}
        onClose={() => setMentorOpen(false)}
      />
    </section>
  );
}

function Stat({ icon: Icon, label, value, note }: { icon: typeof Wallet; label: string; value: string; note: string }) {
  return (
    <div className="flex flex-col gap-1 px-4 py-4 md:px-6">
      <dt className="inline-flex items-center gap-1.5 text-caption text-muted-foreground">
        <Icon aria-hidden className="size-3.5" />
        {label}
      </dt>
      <dd className="text-h2 text-foreground">{value}</dd>
      <dd className="text-caption text-muted-foreground">{note}</dd>
    </div>
  );
}

/** 최근 팀 세션 3개 (A73 팀 필터) */
function RecentSessions({ teamId }: { teamId: string }) {
  const sessions = useQuery(teamSessionsQuery(teamId));
  const items = sessions.data?.items ?? [];
  return (
    <div className="flex flex-col border-t border-border pb-2">
      <div className="flex items-center justify-between px-4 pt-4 pb-2 md:px-6">
        <p className="text-caption text-muted-foreground">최근 팀 세션</p>
        <Link to="/mentoring/sessions" className="text-caption text-primary-text hover:underline">
          진행 기록에서 모두 보기
        </Link>
      </div>
      {sessions.isPending ? (
        <div className="flex justify-center py-4">
          <Spinner />
        </div>
      ) : items.length === 0 ? (
        <p className="px-4 py-3 text-body-sm text-muted-foreground md:px-6">아직 팀 세션이 없어요</p>
      ) : (
        <ul>
          {items.map((s) => {
            const style = STATUS_STYLE[s.status];
            return (
              <li key={s.id}>
                <Link
                  to="/mentoring/sessions/$sessionId"
                  params={{ sessionId: s.id }}
                  aria-label={`${s.title} · ${style.label}`}
                  className="flex items-center gap-3 px-4 py-2.5 outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring md:px-6"
                >
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5 md:flex-row md:items-center md:gap-6">
                    <span className="shrink-0 font-mono text-body-sm text-foreground md:w-36">
                      {formatKstDayTime(s.starts_at)}
                    </span>
                    <span className="truncate text-body text-foreground">
                      {s.title} · {s.topic}
                    </span>
                  </span>
                  <Badge variant={style.badge}>{style.label}</Badge>
                  <ChevronRight aria-hidden className="size-4 text-muted-foreground" />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/** 팀-담당 멘토 방으로 (F41). 방이 없으면(담당 멘토에게 팀 신청이 없으면) 숨긴다 */
function TeamChatButton({ team }: { team: StudentTeam }) {
  const threads = useInfiniteQuery(threadsQuery);
  const thread = findThread(threads.data, { mentorId: team.mentor.mentor_id, teamId: team.id });
  if (!thread) return null;
  return (
    <Button asChild variant="outline" size="sm" className="h-10 md:h-8">
      <Link to="/mentoring/chat/$threadId" params={{ threadId: thread.id }}>
        <MessageSquare aria-hidden />팀 채팅
      </Link>
    </Button>
  );
}
