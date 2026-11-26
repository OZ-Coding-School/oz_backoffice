import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  ArrowLeft,
  CalendarDays,
  ChevronRight,
  Clock,
  FileSearch,
  Hourglass,
  MessageSquare,
  User,
  Users,
} from "lucide-react";
import { useState } from "react";

import { ApiError } from "@/api/errors";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Markdown } from "@/components/markdown";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { findThread, threadsQuery } from "@/features/chat/api";
import { ENROLLMENT_STATUS_LABELS } from "@/features/member/api";
import { requestQuery, type MentoringRequest } from "@/features/requests/api";
import { canceledTail } from "@/features/requests/labels";
import { formatKst, formatKstDay, formatKstDayTime } from "@/lib/datetime";

import { RECEIVED_STATUS } from "../labels";
import { ApprovePanel, RejectPanel } from "./decision-panels";

/** 받은 신청 상세 (Figma `Column / 받은 신청 · 상세 (FE-9b)`, F45·A43·A76) */
export function ReceivedRequestPage({ requestId }: { requestId: string }) {
  const detail = useQuery(requestQuery(requestId));
  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <Link
        to="/mentor/requests"
        className="inline-flex w-fit items-center gap-1.5 text-body-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft aria-hidden className="size-4" />
        받은 신청
      </Link>
      {detail.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : detail.isError ? (
        detail.error instanceof ApiError && detail.error.status === 404 ? (
          <EmptyState
            icon={FileSearch}
            title="신청을 찾을 수 없어요"
            description="볼 수 없는 신청이에요. 받은 신청에서 다시 골라 주세요."
          />
        ) : (
          <ErrorState onRetry={() => void detail.refetch()} />
        )
      ) : (
        <Detail request={detail.data} />
      )}
    </div>
  );
}

function Detail({ request }: { request: MentoringRequest }) {
  // 화면을 연 시각으로 지난 일시를 가린다 (최종 판정은 서버, desired_time_passed)
  const [now] = useState(() => Date.now());
  const pending = request.status === "PENDING";
  return (
    // 데스크톱은 2단, 그 밖은 머리·요약 → 패널 → 신청 내용 순 (F45)
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_22.5rem] lg:items-start lg:gap-6">
      <article className="flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm lg:row-span-2">
        <Hero request={request} />
        <Facts request={request} />
        <Body request={request} className="hidden lg:flex" />
      </article>
      <aside className="flex flex-col gap-4">
        {pending ? (
          <>
            <ApprovePanel request={request} now={now} />
            <RejectPanel request={request} />
          </>
        ) : (
          <ResultCard request={request} />
        )}
        <ChatLink request={request} />
      </aside>
      <section className="flex flex-col rounded-2xl border border-border bg-card shadow-sm lg:hidden">
        <Body request={request} />
      </section>
    </div>
  );
}

function Hero({ request }: { request: MentoringRequest }) {
  const style = RECEIVED_STATUS[request.status];
  const KindIcon = request.team_id ? Users : User;
  const cohort = cohortName(request);
  return (
    <header className="flex flex-col gap-3 bg-accent px-4 py-6 md:px-7">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 rounded-full bg-background px-2 py-0.5 text-caption-strong text-accent-foreground">
          <KindIcon aria-hidden className="size-3.5" />
          {request.team_id ? "팀 멘토링" : "1:1 멘토링"}
          {cohort ? ` · ${cohort}` : ""}
        </span>
        <Badge variant={request.status === "PENDING" ? "primary" : style.badge}>
          {request.status === "PENDING" ? "승인 대기" : style.label}
        </Badge>
      </div>
      <h1 className="text-display text-foreground">{request.topic}</h1>
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <span className="text-caption text-muted-foreground">신청자</span>
        <Avatar name={request.requester_name} size="sm" />
        <span className="text-body-strong text-foreground">
          {request.team_id ? `${request.team_label ?? "팀"} · ${request.requester_name}` : request.requester_name}
        </span>
        <span className="text-caption text-muted-foreground">
          {[cohort, request.requester_status ? ENROLLMENT_STATUS_LABELS[request.requester_status] : null]
            .filter(Boolean)
            .join(" · ")}
        </span>
      </div>
    </header>
  );
}

function Facts({ request }: { request: MentoringRequest }) {
  const deadline = [...request.desired_times].sort().at(-1);
  return (
    <dl className="grid grid-cols-1 border-y border-border md:grid-cols-3 md:divide-x md:divide-border max-md:divide-y max-md:divide-border">
      <Fact
        icon={CalendarDays}
        label="신청일"
        value={request.created_at ? formatKstDayTime(request.created_at) : "-"}
        note={request.team_id ? "팀 신청" : "나에게 보낸 1:1 신청"}
      />
      <Fact
        icon={Clock}
        label="진행 시간"
        value={`${request.duration}분`}
        note={request.team_id ? "팀 시간에서 차감 예정" : "신청자 시간에서 차감 예정"}
      />
      {request.status === "PENDING" && deadline ? (
        <Fact icon={Hourglass} label="승인 기한" value={`${dayTime(deadline)} 전`} note="지나면 자동 만료" />
      ) : (
        <Fact
          icon={Hourglass}
          label="처리"
          value={RECEIVED_STATUS[request.status].label}
          note={processedNote(request)}
        />
      )}
    </dl>
  );
}

function Fact({ icon: Icon, label, value, note }: { icon: typeof Clock; label: string; value: string; note: string }) {
  return (
    <div className="flex flex-col gap-1 px-4 py-3.5 md:px-7">
      <dt className="inline-flex items-center gap-1.5 text-caption text-muted-foreground">
        <Icon aria-hidden className="size-3.5" />
        {label}
      </dt>
      <dd className="text-body-strong text-foreground">{value}</dd>
      <dd className="text-caption text-muted-foreground">{note}</dd>
    </div>
  );
}

function Body({ request, className }: { request: MentoringRequest; className?: string }) {
  return (
    <div className={`flex flex-col gap-2.5 px-4 py-6 md:px-7 ${className ?? "flex"}`}>
      <h2 className="text-body-strong text-foreground">신청 내용</h2>
      <div className="rounded-lg border border-border bg-muted px-4 py-4">
        <Markdown>{request.detail}</Markdown>
      </div>
    </div>
  );
}

/** 처리 결과 카드 (F45): 승인·반려·취소 */
function ResultCard({ request }: { request: MentoringRequest }) {
  const rows: [string, string][] =
    request.status === "APPROVED"
      ? [
          ["확정 일시", request.session ? `${sessionRange(request.session)}${rankNote(request)}` : "-"],
          ["안내", "세션과 Meet 링크가 만들어졌고 신청자에게 채팅으로 알렸어요"],
        ]
      : request.status === "REJECTED"
        ? [
            ["반려 사유", request.reject_reason ?? "-"],
            ["반려 시각", request.rejected_at ? formatKstDayTime(request.rejected_at) : "-"],
          ]
        : [
            ["취소 사유", request.cancel_reason ?? "-"],
            ["취소", canceledTail(request, false) || "-"],
          ];
  const title =
    request.status === "APPROVED"
      ? "승인한 신청이에요"
      : request.status === "REJECTED"
        ? "반려한 신청이에요"
        : "취소된 신청이에요";
  return (
    <section aria-label="처리 결과" className="flex flex-col gap-3 rounded-2xl border border-border bg-card shadow-sm p-5">
      <h2 className="text-h3 text-foreground">{title}</h2>
      <dl className="flex flex-col gap-2.5">
        {rows.map(([label, value]) => (
          <div key={label} className="flex flex-col gap-0.5">
            <dt className="text-caption text-muted-foreground">{label}</dt>
            <dd className="text-body text-foreground break-words whitespace-pre-wrap">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** 그 상대와의 방이 있을 때만 (F41·F45) */
function ChatLink({ request }: { request: MentoringRequest }) {
  const threads = useInfiniteQuery(threadsQuery);
  const thread = findThread(threads.data, {
    mentorId: request.mentor_id,
    teamId: request.team_id,
    studentId: request.requester_id,
  });
  if (!thread) return null;
  const who = request.team_id ? (request.team_label ?? "팀") : request.requester_name;
  return (
    <Link
      to="/mentoring/chat/$threadId"
      params={{ threadId: thread.id }}
      className="flex items-center gap-2.5 rounded-2xl border border-border bg-card shadow-sm px-5 py-3.5 text-body text-foreground outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
    >
      <MessageSquare aria-hidden className="size-4 text-muted-foreground" />
      <span className="flex-1">{who}과의 채팅에서 먼저 물어보기</span>
      <ChevronRight aria-hidden className="size-4 text-muted-foreground" />
    </Link>
  );
}

function cohortName(request: Pick<MentoringRequest, "bootcamp_name" | "cohort_number">): string | null {
  return request.bootcamp_name && request.cohort_number ? `${request.bootcamp_name} ${request.cohort_number}기` : null;
}

function dayTime(iso: string): string {
  return `${formatKstDay(iso)} ${formatKst(iso, "HH:mm")}`;
}

function sessionRange(session: NonNullable<MentoringRequest["session"]>): string {
  return `${dayTime(session.starts_at)} ~ ${formatKst(session.ends_at, "HH:mm")}`;
}

function rankNote(request: MentoringRequest): string {
  const chosen = request.session?.starts_at;
  if (!chosen) return "";
  const rank = request.desired_times.findIndex((t) => Date.parse(t) === Date.parse(chosen));
  return rank >= 0 ? ` · ${rank + 1}순위` : "";
}

function processedNote(request: MentoringRequest): string {
  if (request.status === "APPROVED" && request.session) return sessionRange(request.session);
  if (request.status === "REJECTED" && request.rejected_at) return formatKstDayTime(request.rejected_at);
  if (request.status === "CANCELED" && request.canceled_at) return formatKstDayTime(request.canceled_at);
  return "";
}
