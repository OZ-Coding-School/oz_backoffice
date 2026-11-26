import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, FileSearch, FileText, Video } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { CardTitle } from "@/components/section-card";
import { ApiError } from "@/api/errors";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Markdown } from "@/components/markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { sessionQuery, type MentoringSession } from "@/features/sessions/api";
import { ReplaySection } from "@/features/sessions/components/replay-section";
import { plannedMinutes, scheduleLabel } from "@/features/sessions/labels";
import { formatKstDayTime } from "@/lib/datetime";

import { noteQuery, useSaveNote } from "../api";
import { canEnterMeet, mentorStatus, recordState, targetLabel } from "../labels";
import { NOTE_FALLBACK_MESSAGE } from "../messages";
import { NOTE_MAX_LENGTH } from "../schemas";
import { RecordCard } from "./record-card";

/** 멘토 세션 상세 (Figma `Column / 세션 · 상세·기록 (FE-10b)`, F48·A53·A78) */
export function MentorSessionPage({ sessionId }: { sessionId: string }) {
  const detail = useQuery(sessionQuery(sessionId));
  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <Link
        to="/mentor/sessions"
        className="inline-flex w-fit items-center gap-1.5 text-body-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft aria-hidden className="size-4" />
        세션
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
            description="볼 수 없는 세션이에요. 세션 목록에서 다시 골라 주세요."
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
  // 화면을 연 시각으로 시작 전·진행됨을 나눈다 (최종 판정은 서버, session_not_started)
  const [now] = useState(() => Date.now());
  const record = recordState(session, now);
  const status =
    record.kind === "missing" ? { label: "기록 미제출", badge: "destructive" as const } : mentorStatus(session, now);
  const cohort =
    session.bootcamp_name && session.cohort_number ? `${session.bootcamp_name} ${session.cohort_number}기` : null;
  return (
    <>
      <header className="flex flex-col gap-3 md:flex-row md:items-start">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-h1 text-foreground">{session.title}</h1>
            <Badge variant={status.badge}>{status.label}</Badge>
          </div>
          <p className="text-body text-muted-foreground">
            {[scheduleLabel(session), targetLabel(session), cohort].filter(Boolean).join(" · ")}
          </p>
        </div>
        {canEnterMeet(session, now) ? (
          <Button asChild className="max-md:w-full">
            <a href={session.google_meet_url ?? undefined} target="_blank" rel="noopener noreferrer">
              <Video aria-hidden />
              Meet 입장
            </a>
          </Button>
        ) : null}
      </header>
      {/* 완료 세션은 머리 아래 전체 폭으로 다시 보기 (F50, 수강생 FE-5b와 같은 블록) */}
      {session.status === "COMPLETED" ? <ReplaySection session={session} /> : null}
      {/* 데스크톱은 2단, 그 밖은 기록 → 신청 정보 → 내부 메모 (F48) */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_22.5rem] lg:items-start lg:gap-6">
        <RecordCard session={session} now={now} />
        <aside className="flex flex-col gap-4">
          <RequestInfo session={session} />
          <NoteCard sessionId={session.id} />
        </aside>
      </div>
    </>
  );
}

function RequestInfo({ session }: { session: MentoringSession }) {
  return (
    <section
      aria-label="신청 정보"
      className="flex flex-col gap-3 rounded-2xl border border-border bg-card shadow-sm p-5"
    >
      <CardTitle icon={FileText}>신청 정보</CardTitle>
      <dl className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-x-4 gap-y-2 text-body">
        <dt className="text-caption text-muted-foreground">신청 시간</dt>
        <dd className="text-foreground">{plannedMinutes(session)}분</dd>
        {session.requested_at ? (
          <>
            <dt className="text-caption text-muted-foreground">신청일</dt>
            <dd className="text-foreground">{formatKstDayTime(session.requested_at)}</dd>
          </>
        ) : null}
      </dl>
      {session.detail ? (
        <div className="rounded-lg bg-muted px-4 py-3">
          <Markdown>{session.detail}</Markdown>
        </div>
      ) : null}
    </section>
  );
}

/** 내부 메모 (5,000자, 운영진도 보고 수강생은 못 본다) */
function NoteCard({ sessionId }: { sessionId: string }) {
  const note = useQuery(noteQuery(sessionId));
  const save = useSaveNote(sessionId);
  const [draft, setDraft] = useState<string | null>(null);
  const value = draft ?? note.data?.body ?? "";
  const text = value.trim();
  const onSave = async () => {
    try {
      await save.mutateAsync(text);
      setDraft(null);
      toast.success("메모를 저장했어요");
    } catch {
      toast.error(NOTE_FALLBACK_MESSAGE);
    }
  };
  return (
    <section
      aria-labelledby="note-title"
      className="flex flex-col gap-3 rounded-2xl border border-border bg-card shadow-sm p-5"
    >
      <div className="flex items-center gap-2">
        <h2 id="note-title" className="flex-1 text-h3 text-foreground">
          내부 메모
        </h2>
        <Badge variant="outline">운영진만</Badge>
      </div>
      <Textarea
        aria-labelledby="note-title"
        rows={5}
        maxLength={NOTE_MAX_LENGTH}
        value={value}
        disabled={note.isPending}
        placeholder="다음 세션 준비나 운영진에게 남길 내용을 적어요. 수강생에게는 보이지 않아요."
        onChange={(e) => setDraft(e.target.value)}
      />
      <div className="flex items-center justify-between gap-2">
        <span className="text-caption text-muted-foreground">
          {note.data?.updated_at && draft === null ? `${formatKstDayTime(note.data.updated_at)} 저장` : ""}
        </span>
        <span className="text-caption text-muted-foreground">
          {value.length.toLocaleString()} / {NOTE_MAX_LENGTH.toLocaleString()}
        </span>
      </div>
      <Button
        variant="outline"
        size="sm"
        className="w-fit"
        disabled={!text || draft === null || save.isPending}
        onClick={() => void onSave()}
      >
        메모 저장
      </Button>
    </section>
  );
}
