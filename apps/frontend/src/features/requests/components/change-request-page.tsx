import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, FileSearch, Info, User, Users } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Alert } from "@/components/ui/alert";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { ContentStep } from "@/features/apply/components/content-step";
import { ScheduleStep } from "@/features/apply/components/schedule-step";
import { CREATE_ERROR_MESSAGES, CREATE_FALLBACK_MESSAGE } from "@/features/apply/messages";
import { contentSchema, type ContentForm } from "@/features/apply/schemas";
import { activeCohort, enrollmentsQuery } from "@/features/member/api";

import { balancesQuery, mentoringSettingsQuery, requestQuery, useChangeRequest, type MentoringRequest } from "../api";
import { cancelState, kindLabel } from "../labels";
import { CHANGE_EXTRA_MESSAGES } from "../messages";

/**
 * 신청 변경 (Figma `Column / 신청 변경 (FE-4b)`, F32·A44).
 * 같은 멘토·종류로 기존 신청을 취소하고 새 신청을 만든다. 고친 값은 임시 저장하지 않는다.
 */
export function ChangeRequestPage({ requestId }: { requestId: string }) {
  const request = useQuery(requestQuery(requestId));
  return (
    <div className="flex flex-col gap-6">
      <Link
        to="/mentoring/requests/$requestId"
        params={{ requestId }}
        className="inline-flex w-fit items-center gap-1.5 text-body-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft aria-hidden className="size-4" />
        신청 상세
      </Link>
      {request.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : request.isError ? (
        request.error instanceof ApiError && request.error.status === 404 ? (
          <EmptyState icon={FileSearch} title="신청을 찾을 수 없어요" />
        ) : (
          <ErrorState onRetry={() => void request.refetch()} />
        )
      ) : (
        <ChangeForm request={request.data} />
      )}
    </div>
  );
}

function ChangeForm({ request }: { request: MentoringRequest }) {
  const navigate = useNavigate();
  const enrollments = useQuery(enrollmentsQuery);
  const enrollment = enrollments.data?.find((e) => e.student_id === request.requester_id);
  const active = enrollments.data ? activeCohort(enrollments.data) : null;
  const cohortId = enrollment?.cohort_id ?? "";
  const mine = !!enrollment;
  const enrolled = mine && active?.readOnly === false;
  const settings = useQuery({ ...mentoringSettingsQuery(cohortId), enabled: enrolled });
  const balances = useQuery({ ...balancesQuery, enabled: enrolled });
  // 화면을 연 시각 기준으로 마감을 본다 (최종 판정은 서버)
  const [now] = useState(() => new Date());
  const state = cancelState(request, { mine, minLeadHours: settings.data?.min_lead_hours, now });
  const [duration, setDuration] = useState(request.duration);
  const [desiredTimes, setDesiredTimes] = useState(() =>
    request.desired_times.filter((t) => new Date(t).getTime() > now.getTime()),
  );
  const form = useForm<ContentForm>({
    resolver: zodResolver(contentSchema),
    defaultValues: { topic: request.topic, detail: request.detail },
  });
  const change = useChangeRequest(request.id);
  const [serverError, setServerError] = useState<string | null>(null);

  if (enrollments.isPending || (enrolled && (settings.isPending || balances.isPending))) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }
  if (state.kind !== "available" || !settings.data) {
    return (
      <EmptyState
        icon={FileSearch}
        title="이 신청은 바꿀 수 없어요"
        description={
          state.kind === "deadline_passed"
            ? "변경 마감이 지났어요. 운영진에게 문의해 주세요."
            : "신청한 사람만 승인 대기 중이거나 마감 전인 신청을 바꿀 수 있어요."
        }
      />
    );
  }

  const account = (balances.data ?? []).find((a) =>
    request.team_id
      ? a.owner_type === "TEAM" && a.owner_id === request.team_id
      : a.owner_type === "STUDENT" && a.owner_id === request.requester_id,
  );
  // 기존 신청을 먼저 취소하므로 그 시간을 돌려받은 뒤의 남은 시간으로 고른다
  const giveBack = request.balance.state === "HELD" || request.balance.state === "USED" ? request.balance.minutes : 0;
  const remaining = (account?.remaining_minutes ?? 0) + giveBack;
  const mentor = {
    mentor_id: request.mentor_id,
    display_name: request.mentor_display_name,
    headline: request.mentor_headline,
    expertise: null,
    profile_image_url: null,
  };
  const KindIcon = request.team_id ? Users : User;

  const save = form.handleSubmit(async ({ topic, detail }) => {
    setServerError(null);
    try {
      const created = await change.mutateAsync({ topic, detail, desiredTimes, duration });
      toast.success("신청을 바꿨어요");
      await navigate({ to: "/mentoring/requests/$requestId", params: { requestId: created.id }, replace: true });
    } catch (error) {
      const code = error instanceof ApiError ? error.code : "";
      setServerError(CHANGE_EXTRA_MESSAGES[code] ?? CREATE_ERROR_MESSAGES[code] ?? CREATE_FALLBACK_MESSAGE);
    }
  });

  return (
    <form onSubmit={(e) => void save(e)} className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">신청 변경</h1>
        <p className="text-body text-muted-foreground">
          {request.mentor_display_name}에게 보낸 {request.team_id ? "팀" : "1:1"} 신청을 바꿔요. 저장하면 기존 신청은 새
          신청으로 바뀌어요.
        </p>
      </div>
      {request.status === "APPROVED" ? (
        <Alert
          variant="warning"
          title="저장하면 확정된 세션이 취소돼요"
          description="차감된 시간은 돌려받고, 새 신청은 멘토의 승인을 다시 기다려요. 지금 잡힌 시간은 다시 고를 수 없어요."
        />
      ) : null}
      <div className="flex flex-wrap items-center gap-2.5 rounded-xl border border-border bg-muted px-4 py-3">
        <Avatar name={request.mentor_display_name} size="sm" />
        <span className="inline-flex items-center gap-1 text-body-strong text-foreground">
          <KindIcon aria-hidden className="size-3.5" />
          {request.mentor_display_name} · {kindLabel(request)}
        </span>
        <span className="text-caption text-muted-foreground">멘토와 멘토링 종류는 바꿀 수 없어요</span>
      </div>
      <Section number={1} title="일정" />
      <ScheduleStep
        cohortId={cohortId}
        mentor={mentor}
        unit={settings.data.allowed_duration}
        remaining={remaining}
        duration={duration}
        desiredTimes={desiredTimes}
        onChange={(patch) => {
          if (patch.duration !== undefined) setDuration(patch.duration);
          if (patch.desiredTimes) setDesiredTimes(patch.desiredTimes);
        }}
      />
      <Section number={2} title="신청 내용" />
      <ContentStep form={form} />
      {serverError ? <Alert variant="error" title={serverError} /> : null}
      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card shadow-sm px-5 py-4 md:flex-row md:items-center">
        <p className="flex flex-1 items-start gap-2 text-caption text-muted-foreground">
          <Info aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          진행 시간을 바꾸면 차감 예정 시간도 그만큼 다시 잡혀요
        </p>
        <div className="flex gap-2">
          <Button variant="ghost" className="flex-1 md:flex-none" asChild>
            <Link to="/mentoring/requests/$requestId" params={{ requestId: request.id }}>
              취소
            </Link>
          </Button>
          <Button
            type="submit"
            className="flex-1 md:flex-none"
            disabled={change.isPending || desiredTimes.length === 0}
          >
            변경 저장
          </Button>
        </div>
      </div>
    </form>
  );
}

function Section({ number, title }: { number: number; title: string }) {
  return (
    <h2 className="flex items-center gap-2 text-h3 text-foreground">
      <span
        aria-hidden
        className="inline-flex size-5.5 items-center justify-center rounded-full bg-primary text-caption-strong text-primary-foreground"
      >
        {number}
      </span>
      {title}
    </h2>
  );
}
