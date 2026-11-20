import { Link } from "@tanstack/react-router";
import { ChevronRight, Info, TriangleAlert, User, Users } from "lucide-react";

import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import type { MentoringSession } from "../api";
import { cancelNote, isMine, kindLabel, NO_SHOW_NOTE, STATUS_STYLE, timeBlock } from "../labels";

/**
 * 세션 카드 (Figma `Screen / 진행 기록`, F33).
 * 데스크톱·태블릿은 왼쪽에 시각, 모바일은 위쪽 띠로 올린다.
 */
export function SessionCard({ session, myStudentIds }: { session: MentoringSession; myStudentIds: Set<string> }) {
  const style = STATUS_STYLE[session.status];
  const time = timeBlock(session);
  const KindIcon = session.team_id ? Users : User;
  return (
    <Link
      to="/mentoring/sessions/$sessionId"
      params={{ sessionId: session.id }}
      aria-label={`${session.title} · ${style.label}`}
      className={cn(
        "flex overflow-hidden rounded-xl border border-border outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
        style.card,
      )}
    >
      <span aria-hidden className={cn("w-1 shrink-0", style.bar)} />
      <div className="flex min-w-0 flex-1 flex-col md:flex-row">
        <div
          className={cn(
            "flex items-center gap-1.5 border-b border-border/60 px-4 py-2.5 md:w-40 md:shrink-0 md:flex-col md:items-start md:gap-1 md:border-r md:border-b-0 md:px-5 md:py-5 lg:w-46",
            style.side,
          )}
        >
          <span className="text-caption text-muted-foreground">{time.label}</span>
          <span className="text-body-strong text-foreground">{time.day}</span>
          <span className="font-mono text-body-sm text-foreground">{time.range}</span>
          <span className="ml-auto text-caption text-muted-foreground md:ml-0">{time.note}</span>
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-2.5 px-4 pt-3.5 pb-4 md:px-5 md:py-4.5">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 text-caption text-muted-foreground">
              <KindIcon aria-hidden className="size-3.5" />
              {kindLabel(session)}
            </span>
            <Badge variant={style.badge} className="ml-auto">
              {style.label}
            </Badge>
          </div>
          <h2 className="text-h3 text-foreground">{session.title}</h2>
          <Row label="멘토">
            <span className="flex min-w-0 items-center gap-2">
              <Avatar name={session.mentor_display_name} size="sm" />
              <span className="text-body-strong text-foreground">{session.mentor_display_name}</span>
              {session.mentor_headline ? (
                <span className="truncate text-caption text-muted-foreground">{session.mentor_headline}</span>
              ) : null}
            </span>
          </Row>
          <Row label="주제">
            <span className="text-body text-foreground">{session.topic}</span>
          </Row>
          <Row label="참여자">
            <ParticipantChips session={session} myStudentIds={myStudentIds} />
          </Row>
          <SessionNote session={session} mine={isMine(session, myStudentIds)} />
        </div>
        <span aria-hidden className="hidden items-center pr-4 text-muted-foreground md:flex">
          <ChevronRight className="size-4.5" />
        </span>
      </div>
    </Link>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 items-start gap-2">
      <span className="w-14 shrink-0 pt-0.5 text-caption text-muted-foreground">{label}</span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export function ParticipantChips({
  session,
  myStudentIds,
}: {
  session: Pick<MentoringSession, "participants">;
  myStudentIds: Set<string>;
}) {
  return (
    <ul className="flex flex-wrap gap-1.5">
      {session.participants.map((p) => (
        <li
          key={p.student_id}
          className="inline-flex items-center gap-1 rounded-full border border-border bg-background py-0.5 pr-2 pl-1"
        >
          <Avatar name={p.name} size="sm" className="size-5" />
          <span className="text-caption text-foreground">
            {p.name}
            {myStudentIds.has(p.student_id) ? " (나)" : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** 노쇼 안내 · 취소 사유 상자 */
export function SessionNote({ session, mine }: { session: MentoringSession; mine: boolean }) {
  if (session.status === "NO_SHOW") {
    return (
      <p className="flex items-start gap-2 rounded-md bg-destructive/15 px-3 py-2 text-body-sm text-foreground">
        <TriangleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
        <span className="min-w-0">{NO_SHOW_NOTE}</span>
      </p>
    );
  }
  const text = cancelNote(session, mine);
  if (!text) return null;
  return (
    <p className="flex items-start gap-2 rounded-md bg-warning/20 px-3 py-2 text-body-sm text-foreground">
      <Info aria-hidden className="mt-0.5 size-3.5 shrink-0" />
      <span className="min-w-0">{text}</span>
    </p>
  );
}
