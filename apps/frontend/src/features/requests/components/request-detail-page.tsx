import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, CalendarDays, Clock, FileSearch, User, Users } from "lucide-react";
import { useMemo, useState } from "react";

import { ApiError } from "@/api/errors";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Markdown } from "@/components/markdown";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { activeCohort, enrollmentsQuery } from "@/features/member/api";
import { formatKst, formatKstDay, formatKstDayTime, formatMinutes } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { balancesQuery, mentoringSettingsQuery, requestQuery, type MentoringRequest } from "../api";
import { cancelState, kindLabel, STATUS_STYLE } from "../labels";
import { CancelRequestDialog } from "./cancel-request-dialog";
import { StatusNote } from "./request-card";

/** 신청 상세 (Figma `Screen / 신청 상세 · 승인 대기 / 승인`, A66·F29). [신청 변경]은 FE-4b에서 추가한다. */
export function RequestDetailPage({ requestId }: { requestId: string }) {
  const detail = useQuery(requestQuery(requestId));
  return (
    <div className="flex flex-col gap-6">
      <Link
        to="/mentoring/requests"
        className="inline-flex w-fit items-center gap-1.5 text-body-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft aria-hidden className="size-4" />
        신청 내역
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
            description="삭제됐거나 볼 수 없는 신청이에요. 신청 내역에서 다시 골라 주세요."
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
  const enrollments = useQuery(enrollmentsQuery);
  const mine = useMemo(
    () => (enrollments.data ?? []).some((e) => e.student_id === request.requester_id),
    [enrollments.data, request.requester_id],
  );
  const cohortId = enrollments.data?.find((e) => e.student_id === request.requester_id)?.cohort_id;
  const active = enrollments.data ? activeCohort(enrollments.data) : null;
  // 취소 마감(min_lead_hours)은 승인된 신청에만 필요하다. 설정 요약은 수강 중 기수만 볼 수 있다 (A64)
  const needsDeadline = mine && request.status === "APPROVED" && !!cohortId && active?.readOnly === false;
  const settings = useQuery({ ...mentoringSettingsQuery(cohortId ?? ""), enabled: needsDeadline });
  // 화면을 연 시각 기준으로 마감을 본다 (최종 판정은 서버, cancel_deadline_passed)
  const [now] = useState(() => new Date());
  const cancel = cancelState(request, { mine, minLeadHours: settings.data?.min_lead_hours, now });
  const style = STATUS_STYLE[request.status];
  const KindIcon = request.team_id ? Users : User;
  const [open, setOpen] = useState(false);
  const showSide = request.status === "PENDING" || request.status === "APPROVED";

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:gap-6">
      <article className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card">
        <header className={cn("flex flex-col gap-3 px-4 py-6 md:px-7", style.card)}>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-full bg-background px-2 py-0.5 text-caption-strong text-accent-foreground">
              <KindIcon aria-hidden className="size-3.5" />
              {kindLabel(request)}
            </span>
            <Badge variant={style.badge}>{style.label}</Badge>
          </div>
          <h1 className="text-display text-foreground">{request.topic}</h1>
          <div className="flex items-center gap-2.5">
            <Avatar name={request.mentor_display_name} />
            <div className="flex min-w-0 flex-col">
              <span className="text-body-strong text-foreground">{request.mentor_display_name}</span>
              {request.mentor_headline ? (
                <span className="text-caption text-muted-foreground">{request.mentor_headline}</span>
              ) : null}
            </div>
          </div>
        </header>
        <dl className="grid grid-cols-1 border-y border-border md:grid-cols-3 md:divide-x md:divide-border">
          <Fact
            icon={CalendarDays}
            label="신청일"
            value={request.created_at ? formatKstDayTime(request.created_at) : "-"}
          />
          <Fact icon={Clock} label="진행 시간" value={`${request.duration}분`} />
          <Fact icon={User} label="신청자" value={`${request.requester_name}${mine ? " (나)" : ""}`} />
        </dl>
        <div className="flex flex-col gap-7 px-4 py-6 md:px-7">
          {request.status === "REJECTED" || request.status === "CANCELED" ? (
            <StatusNote request={request} mine={mine} />
          ) : null}
          <Times request={request} />
          <section className="flex flex-col gap-2.5">
            <div className="flex items-center justify-between">
              <h2 className="text-body-strong text-foreground">신청 내용</h2>
            </div>
            <div className="rounded-lg border border-border bg-muted px-4 py-4">
              <Markdown>{request.detail}</Markdown>
            </div>
          </section>
        </div>
      </article>
      {showSide ? (
        <aside className="flex flex-col gap-4 lg:w-80 lg:shrink-0">
          <BalanceBox
            request={request}
            deadline={cancel.kind === "available" ? cancel.deadline : null}
            leadHours={settings.data?.min_lead_hours}
          />
          {cancel.kind === "available" ? (
            <section className="flex flex-col gap-2 rounded-xl border border-border bg-card p-5">
              <h2 className="text-body-strong text-foreground">
                {request.status === "APPROVED"
                  ? `시작 ${settings.data?.min_lead_hours ?? ""}시간 전까지 취소할 수 있어요`
                  : "승인 전이라 취소할 수 있어요"}
              </h2>
              <Button variant="outline" className="text-destructive-text" onClick={() => setOpen(true)}>
                신청 취소
              </Button>
            </section>
          ) : cancel.kind === "deadline_passed" ? (
            <p className="rounded-xl border border-border bg-card p-5 text-body-sm text-muted-foreground">
              취소 마감이 지났어요. 운영진에게 문의해 주세요.
            </p>
          ) : null}
        </aside>
      ) : null}
      <CancelRequestDialog request={request} open={open} onOpenChange={setOpen} />
    </div>
  );
}

function Fact({ icon: Icon, label, value }: { icon: typeof Clock; label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 px-4 py-3.5 md:px-7">
      <dt className="inline-flex items-center gap-1.5 text-caption text-muted-foreground">
        <Icon aria-hidden className="size-3.5" />
        {label}
      </dt>
      <dd className="text-body-strong text-foreground">{value}</dd>
    </div>
  );
}

function Times({ request }: { request: MentoringRequest }) {
  const approved = request.status === "APPROVED" && request.session;
  const chosen = request.session?.starts_at;
  const rank = chosen
    ? request.desired_times.findIndex((t) => new Date(t).getTime() === new Date(chosen).getTime())
    : -1;
  const slots = approved && chosen ? [chosen] : request.desired_times;
  return (
    <section className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-body-strong text-foreground">{approved ? "확정 일시" : "희망 일시"}</h2>
        {request.status === "PENDING" ? (
          <span className="text-caption text-muted-foreground">멘토가 이 중 하나로 승인해요</span>
        ) : approved && rank >= 0 ? (
          <span className="text-caption text-muted-foreground">멘토가 {rank + 1}순위로 승인했어요</span>
        ) : null}
      </div>
      <ul className="grid grid-cols-1 gap-2 md:grid-cols-3">
        {slots.map((t, i) => (
          <li
            key={t}
            className={cn(
              "flex flex-col gap-0.5 rounded-lg border bg-card px-4 py-3",
              approved
                ? "border-success"
                : i === 0 && request.status === "PENDING"
                  ? "border-primary"
                  : "border-border",
            )}
          >
            <span className="text-caption text-primary-text">
              {approved ? `확정${rank >= 0 ? ` · ${rank + 1}순위` : ""}` : `${i + 1}순위`}
            </span>
            <span className="text-body-strong text-foreground">{formatKstDay(t)}</span>
            <span className="font-mono text-body-sm text-foreground">
              {formatKst(t, "HH:mm")} ~{" "}
              {formatKst(new Date(new Date(t).getTime() + request.duration * 60_000), "HH:mm")}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function BalanceBox({
  request,
  deadline,
  leadHours,
}: {
  request: MentoringRequest;
  deadline: Date | null;
  leadHours: number | undefined;
}) {
  const balances = useQuery(balancesQuery);
  const account = (balances.data ?? []).find((a) =>
    request.team_id
      ? a.owner_type === "TEAM" && a.owner_id === request.team_id
      : a.owner_type === "STUDENT" && a.owner_id === request.requester_id,
  );
  const held = request.balance.state === "HELD";
  return (
    <section className="flex flex-col gap-2.5 rounded-xl border border-border bg-card p-5">
      <h2 className="text-body-strong text-foreground">시간</h2>
      {account ? (
        <Line
          label={request.team_id ? "팀 계좌 남은 시간" : "내 1:1 계좌 남은 시간"}
          value={formatMinutes(account.remaining_minutes)}
        />
      ) : null}
      <Line label={held ? "이 신청 차감 예정" : "이 신청 차감됨"} value={formatMinutes(request.balance.minutes)} />
      {held || deadline ? (
        <p className="rounded-md bg-accent px-3 py-2 text-caption text-foreground">
          {held
            ? "멘토가 승인하면 차감이 확정되고, 승인 전에 취소하면 돌려받아요"
            : `시작 ${leadHours ?? ""}시간 전(${deadline ? formatKstDayTime(deadline) : ""})까지 취소하면 ${formatMinutes(request.duration)}을 모두 돌려받아요`}
        </p>
      ) : null}
    </section>
  );
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-caption text-muted-foreground">{label}</span>
      <span className="text-body-strong text-foreground">{value}</span>
    </div>
  );
}
