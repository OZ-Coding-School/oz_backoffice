import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, useNavigate } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";

import { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/error-state";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { cohortLabel } from "@/features/member/api";
import { formatMinutes } from "@/lib/datetime";

import { mentorsQuery, useCreateRequest, type MentorCard } from "../api";
import { useApplyDraft } from "../draft";
import { BLOCK_MESSAGES, useApplyGate, type ApplyKind, type BlockReason } from "../gate";
import { CREATE_ERROR_MESSAGES, CREATE_ERROR_STEP, CREATE_FALLBACK_MESSAGE } from "../messages";
import { contentSchema, type ContentForm } from "../schemas";
import { durationOptions } from "../slots";
import { STEPS, type FormStep } from "../steps";
import { ConfirmStep } from "./confirm-step";
import { ContentStep } from "./content-step";
import { DoneStep } from "./done-step";
import { KindStep } from "./kind-step";
import { MentorStep } from "./mentor-step";
import { ScheduleStep } from "./schedule-step";
import { Stepper } from "./stepper";
import { TeamMentorStep } from "./team-mentor-step";

export type ApplyStep = FormStep | "done";

const BACK: Partial<Record<FormStep, { to: FormStep; label: string }>> = {
  schedule: { to: "mentor", label: "이전: 멘토 선택" },
  content: { to: "schedule", label: "이전: 일정 선택" },
  confirm: { to: "content", label: "이전: 신청 내용" },
};

/** 막혀도 그 종류의 첫 화면(멘토 목록·담당 멘토)은 보여 주고 [다음]만 막는 사유 */
const SHOW_WITH_NOTICE: readonly BlockReason[] = ["no_time", "team_no_time", "mentor_not_accepting"];

/**
 * 멘토링 신청 (Figma `Column / 멘토링 신청 · 1:1 (FE-3a)`·`· 팀·종류 (FE-3b)`, F28·F30·F31).
 * 주소 `/mentoring/apply?kind=&step=`. 1:1·팀을 모두 허용하면 첫 화면이 종류 선택이다.
 */
export function ApplyPage({
  userId,
  kind,
  step,
  requestId,
}: {
  userId: string;
  kind?: ApplyKind;
  step: ApplyStep;
  requestId?: string;
}) {
  if (step === "done") {
    return requestId ? <DoneStep requestId={requestId} /> : <Navigate to="/mentoring/apply" replace />;
  }
  return <ApplyForm userId={userId} kindParam={kind} step={step} />;
}

function ApplyForm({ userId, kindParam, step }: { userId: string; kindParam: ApplyKind | undefined; step: FormStep }) {
  const navigate = useNavigate();
  const gate = useApplyGate();
  const draft = useApplyDraft();
  const update = useApplyDraft((s) => s.update);
  const ensureOwner = useApplyDraft((s) => s.ensureOwner);
  const chooseKind = useApplyDraft((s) => s.chooseKind);
  const reset = useApplyDraft((s) => s.reset);
  const cohortId = gate.cohort?.enrollment.cohort_id ?? "";
  const both = gate.kinds.length > 1;
  const kind: ApplyKind | null =
    kindParam && gate.kinds.includes(kindParam) ? kindParam : gate.kinds.length === 1 ? (gate.kinds[0] ?? null) : null;
  const [picked, setPicked] = useState<ApplyKind | null>(draft.kind);
  const blocked = gate.blocked(kind);
  const showStep = !blocked || SHOW_WITH_NOTICE.includes(blocked);
  const mentors = useQuery({
    ...mentorsQuery(cohortId),
    enabled: !gate.loading && !!gate.settings && kind === "one" && showStep,
  });
  const create = useCreateRequest();
  const [serverError, setServerError] = useState<{ message: string; step?: FormStep } | null>(null);
  const form = useForm<ContentForm>({
    resolver: zodResolver(contentSchema),
    defaultValues: { topic: draft.topic, detail: draft.detail },
  });
  const content = useWatch({ control: form.control });

  // 다른 사용자·기수의 임시 값은 버린다
  useEffect(() => {
    if (cohortId && ensureOwner(`${userId}:${cohortId}`)) form.reset({ topic: "", detail: "" });
  }, [cohortId, userId, ensureOwner, form]);
  // 종류가 정해지면 기억한다(다른 종류였으면 멘토·일정을 비운다, F31)
  useEffect(() => {
    if (kind) chooseKind(kind);
  }, [kind, chooseKind]);
  // 신청 내용은 쓰는 대로 임시 저장한다 (새로고침 유지)
  const topicValue = content.topic ?? "";
  const detailValue = content.detail ?? "";
  const savedTopic = draft.topic;
  const savedDetail = draft.detail;
  useEffect(() => {
    if (savedTopic !== topicValue || savedDetail !== detailValue) update({ topic: topicValue, detail: detailValue });
  }, [topicValue, detailValue, savedTopic, savedDetail, update]);

  const searchOf = (to: FormStep, k: ApplyKind | null = kind) => ({
    ...(both && k ? { kind: k } : {}),
    ...(to === "mentor" ? {} : { step: to }),
  });
  const go = (to: FormStep, k: ApplyKind | null = kind) =>
    void navigate({ to: "/mentoring/apply", search: searchOf(to, k) });

  if (gate.loading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }
  if (gate.error) return <ErrorState onRetry={() => window.location.reload()} />;

  const cohortName = gate.cohort ? cohortLabel(gate.cohort.enrollment) : "";
  // 허용하지 않는 종류로 들어오면 첫 화면으로
  if (kindParam && gate.settings && !gate.kinds.includes(kindParam)) return <Navigate to="/mentoring/apply" replace />;

  // ── 종류 선택 (1:1·팀 모두 허용, F31)
  if (!kind) {
    const top = gate.blocked(null);
    if (step !== "mentor") return <Navigate to="/mentoring/apply" replace />;
    return (
      <div className="flex flex-col gap-6">
        {top ? (
          <Alert variant="warning" title={BLOCK_MESSAGES[top].title} description={BLOCK_MESSAGES[top].description} />
        ) : null}
        {both ? <Stepper kind={null} current="kind" /> : null}
        <div className="flex flex-col gap-1">
          <h1 className="text-h1 text-foreground">어떤 멘토링을 신청할까요?</h1>
          {both ? (
            <p className="text-body text-muted-foreground">
              {cohortName}는 팀 멘토링과 1:1 멘토링을 모두 신청할 수 있어요.
            </p>
          ) : null}
        </div>
        {both && !top ? (
          <>
            <KindStep gate={gate} selected={picked} onSelect={setPicked} />
            <div className="flex justify-end">
              <Button
                className="w-full md:w-auto"
                disabled={!picked || (picked === "team" && !gate.team)}
                onClick={() => picked && go("mentor", picked)}
              >
                다음
              </Button>
            </div>
          </>
        ) : null}
      </div>
    );
  }

  const team = kind === "team" ? gate.team : undefined;
  const account = kind === "team" ? gate.teamAccount : gate.oneAccount;
  const mentor: MentorCard | undefined =
    kind === "team" ? gate.teamMentor : mentors.data?.find((m) => m.mentor_id === draft.mentorId);
  const sameKind = draft.kind === kind;
  const settings = gate.settings;
  const remaining = account?.remaining_minutes ?? 0;
  const unit = settings?.allowed_duration ?? 30;
  const options = durationOptions(unit, remaining);
  const duration = draft.duration && options.includes(draft.duration) ? draft.duration : (options[0] ?? unit);
  const hasMentor = kind === "team" ? !!team : sameKind && !!draft.mentorId;

  // 신청할 수 없으면 첫 단계에서 사유만 보여 준다 (F28)
  if (blocked && step !== "mentor") return <Navigate to="/mentoring/apply" search={searchOf("mentor")} replace />;
  // 앞 단계 값이 없으면 그 단계로 돌려보낸다
  const missing: FormStep | null =
    step !== "mentor" && !hasMentor
      ? "mentor"
      : (step === "content" || step === "confirm") && (!sameKind || draft.desiredTimes.length === 0)
        ? "schedule"
        : step === "confirm" && !contentSchema.safeParse({ topic: draft.topic, detail: draft.detail }).success
          ? "content"
          : null;
  if (!blocked && missing) return <Navigate to="/mentoring/apply" search={searchOf(missing)} replace />;

  const notice = blocked ? BLOCK_MESSAGES[blocked] : null;
  const back =
    step === "mentor"
      ? both
        ? { to: null, label: "이전: 멘토링 종류" }
        : null
      : BACK[step]
        ? { to: BACK[step]!.to, label: kind === "team" && step === "schedule" ? "이전: 멘토 확인" : BACK[step]!.label }
        : null;
  const title =
    step === "mentor"
      ? kind === "team"
        ? `${team?.label ?? "팀"}의 담당 멘토에게 신청해요`
        : "멘토를 골라 주세요"
      : step === "schedule"
        ? "언제 받고 싶나요?"
        : step === "content"
          ? "무엇을 이야기하고 싶나요?"
          : "신청 내용을 확인해 주세요";
  const subtitle =
    step === "mentor"
      ? kind === "team"
        ? "팀 멘토링은 팀의 담당 멘토에게만 신청할 수 있어요. 팀원 누구나 신청할 수 있고, 팀 계좌의 시간을 함께 써요."
        : mentors.data
          ? `지금 신청을 받는 ${cohortName} 멘토 ${mentors.data.length}명이에요. 남은 1:1 시간 ${formatMinutes(remaining)}`
          : ""
      : step === "schedule"
        ? `${mentor?.display_name ?? "멘토"}의 가능한 시간 중 최대 3개를 골라 주세요. 멘토가 그중 하나로 승인해요.`
        : step === "content"
          ? "주제와 미리 볼 내용을 적어 주면 멘토가 준비해 와요."
          : "신청하면 멘토에게 알림이 가고, 승인 전까지 취소할 수 있어요.";

  const next = async () => {
    const index = STEPS.findIndex((s) => s.value === step);
    if (step === "schedule") update({ duration });
    if (step === "mentor" && kind === "team" && team) update({ mentorId: team.mentor.mentor_id });
    if (step === "content" && !(await form.trigger())) return;
    const following = STEPS[index + 1];
    if (following) go(following.value);
  };

  const submit = async () => {
    setServerError(null);
    try {
      const base = {
        topic: draft.topic.trim(),
        detail: draft.detail.trim(),
        desiredTimes: draft.desiredTimes,
        duration,
      };
      const created =
        kind === "team" && team
          ? await create.mutateAsync({ ...base, kind: "team", teamId: team.id })
          : await create.mutateAsync({ ...base, kind: "one", cohortId, mentorId: draft.mentorId ?? "" });
      // 완료 화면으로 먼저 옮긴 뒤 임시 값을 지운다 (먼저 지우면 '앞 단계 값 없음'으로 첫 단계로 돌아간다)
      await navigate({ to: "/mentoring/apply", search: { step: "done", id: created.id }, replace: true });
      reset();
    } catch (error) {
      const code = error instanceof ApiError ? error.code : "";
      setServerError({
        message: CREATE_ERROR_MESSAGES[code] ?? CREATE_FALLBACK_MESSAGE,
        step: CREATE_ERROR_STEP[code],
      });
    }
  };

  const canNext =
    !blocked &&
    (step === "mentor"
      ? kind === "team"
        ? !!team
        : !!mentor
      : step === "schedule"
        ? draft.desiredTimes.length > 0
        : true);

  return (
    <div className="flex flex-col gap-6">
      {notice ? <Alert variant="warning" title={notice.title} description={notice.description} /> : null}
      {back ? (
        <Link
          to="/mentoring/apply"
          search={back.to ? searchOf(back.to) : {}}
          className="inline-flex w-fit items-center gap-1.5 text-body-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft aria-hidden className="size-4" />
          {back.label}
        </Link>
      ) : null}
      <Stepper kind={kind} current={step} />
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">{title}</h1>
        {subtitle ? <p className="text-body text-muted-foreground">{subtitle}</p> : null}
      </div>
      {!showStep ? null : step === "mentor" ? (
        kind === "team" && team ? (
          <TeamMentorStep
            cohortId={cohortId}
            team={team}
            mentor={gate.teamMentor}
            account={account}
            myStudentId={gate.cohort?.enrollment.student_id}
          />
        ) : kind === "one" ? (
          <MentorStep
            cohortId={cohortId}
            selected={sameKind ? draft.mentorId : null}
            onSelect={(id) => update(id === draft.mentorId ? {} : { mentorId: id, desiredTimes: [] })}
          />
        ) : null
      ) : step === "schedule" ? (
        <ScheduleStep
          cohortId={cohortId}
          mentor={mentor}
          unit={unit}
          remaining={remaining}
          duration={duration}
          desiredTimes={draft.desiredTimes}
          onChange={(patch) => update(patch)}
        />
      ) : step === "content" ? (
        <ContentStep form={form} />
      ) : (
        <ConfirmStep
          kind={kind}
          teamLabel={team?.label}
          mentor={mentor}
          duration={duration}
          desiredTimes={draft.desiredTimes}
          topic={draft.topic}
          detail={draft.detail}
          remaining={remaining}
          leadHours={settings?.min_lead_hours}
          onEdit={go}
          submitting={create.isPending}
          onSubmit={() => void submit()}
          error={
            serverError ? (
              <Alert
                variant="error"
                title={serverError.message}
                description={
                  serverError.step ? (
                    <Button variant="link" size="sm" onClick={() => go(serverError.step!)}>
                      {serverError.step === "mentor" ? "멘토 다시 고르기" : "일정 다시 고르기"}
                    </Button>
                  ) : undefined
                }
              />
            ) : null
          }
        />
      )}
      {step !== "confirm" && showStep ? (
        <div className="flex justify-end">
          <Button className="w-full md:w-auto" disabled={!canNext} onClick={() => void next()}>
            다음:{" "}
            {kind === "team" && step === "mentor"
              ? "일정 선택"
              : STEPS[STEPS.findIndex((s) => s.value === step) + 1]?.label}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
