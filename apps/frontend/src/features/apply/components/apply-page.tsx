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

import { mentorsQuery, useCreateRequest } from "../api";
import { useApplyDraft } from "../draft";
import { BLOCK_MESSAGES, useApplyGate } from "../gate";
import { CREATE_ERROR_MESSAGES, CREATE_ERROR_STEP, CREATE_FALLBACK_MESSAGE } from "../messages";
import { contentSchema, type ContentForm } from "../schemas";
import { durationOptions } from "../slots";
import { ConfirmStep } from "./confirm-step";
import { ContentStep } from "./content-step";
import { DoneStep } from "./done-step";
import { MentorStep } from "./mentor-step";
import { ScheduleStep } from "./schedule-step";
import { STEPS, type FormStep } from "../steps";
import { Stepper } from "./stepper";

export type ApplyStep = FormStep | "done";

const HEADS: Record<FormStep, { title: string; back?: { to: FormStep; label: string } }> = {
  mentor: { title: "멘토를 골라 주세요" },
  schedule: { title: "언제 받고 싶나요?", back: { to: "mentor", label: "이전: 멘토 선택" } },
  content: { title: "무엇을 이야기하고 싶나요?", back: { to: "schedule", label: "이전: 일정 선택" } },
  confirm: { title: "신청 내용을 확인해 주세요", back: { to: "content", label: "이전: 신청 내용" } },
};

/** 1:1 멘토링 신청 (Figma `Column / 멘토링 신청 · 1:1 (FE-3a)`, F28·F30). 주소 `/mentoring/apply?step=` */
export function ApplyPage({ userId, step, requestId }: { userId: string; step: ApplyStep; requestId?: string }) {
  if (step === "done") {
    return requestId ? <DoneStep requestId={requestId} /> : <Navigate to="/mentoring/apply" replace />;
  }
  return <ApplyForm userId={userId} step={step} />;
}

function ApplyForm({ userId, step }: { userId: string; step: FormStep }) {
  const navigate = useNavigate();
  const gate = useApplyGate();
  const draft = useApplyDraft();
  const update = useApplyDraft((s) => s.update);
  const ensureOwner = useApplyDraft((s) => s.ensureOwner);
  const reset = useApplyDraft((s) => s.reset);
  const cohortId = gate.cohort?.enrollment.cohort_id ?? "";
  // 남은 시간이 없을 때도 멘토 목록은 보여 주고 [다음]만 막는다 (Figma 신청 막힘 안내)
  const listable = !gate.loading && !gate.error && !!gate.settings && (!gate.blocked || gate.blocked === "no_time");
  const ready = listable;
  const mentors = useQuery({ ...mentorsQuery(cohortId), enabled: ready });
  const mentor = mentors.data?.find((m) => m.mentor_id === draft.mentorId);
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
  // 신청 내용은 쓰는 대로 임시 저장한다 (새로고침 유지)
  const topicValue = content.topic ?? "";
  const detailValue = content.detail ?? "";
  useEffect(() => {
    const current = useApplyDraft.getState();
    if (current.topic !== topicValue || current.detail !== detailValue)
      update({ topic: topicValue, detail: detailValue });
  }, [topicValue, detailValue, update]);

  const go = (to: FormStep) => void navigate({ to: "/mentoring/apply", search: to === "mentor" ? {} : { step: to } });

  if (gate.loading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }
  if (gate.error) return <ErrorState onRetry={() => window.location.reload()} />;

  const settings = gate.settings;
  const remaining = gate.account?.remaining_minutes ?? 0;
  const unit = settings?.allowed_duration ?? 30;
  const options = durationOptions(unit, remaining);
  const duration = draft.duration && options.includes(draft.duration) ? draft.duration : (options[0] ?? unit);

  // 앞 단계 값이 없으면 그 단계로 돌려보낸다
  const missing: FormStep | null =
    step !== "mentor" && !draft.mentorId
      ? "mentor"
      : (step === "content" || step === "confirm") && draft.desiredTimes.length === 0
        ? "schedule"
        : step === "confirm" && !contentSchema.safeParse({ topic: draft.topic, detail: draft.detail }).success
          ? "content"
          : null;
  // 신청할 수 없으면 첫 단계에서 사유만 보여 준다 (F28)
  if (gate.blocked && step !== "mentor") return <Navigate to="/mentoring/apply" search={{}} replace />;
  if (!gate.blocked && missing)
    return <Navigate to="/mentoring/apply" search={missing === "mentor" ? {} : { step: missing }} replace />;

  const head = HEADS[step];
  const blocked = gate.blocked ? BLOCK_MESSAGES[gate.blocked] : null;
  const subtitle =
    step === "mentor"
      ? gate.cohort && mentors.data
        ? `지금 신청을 받는 ${cohortLabel(gate.cohort.enrollment)} 멘토 ${mentors.data.length}명이에요. 남은 1:1 시간 ${formatMinutes(remaining)}`
        : ""
      : step === "schedule"
        ? `${mentor?.display_name ?? "멘토"}의 가능한 시간 중 최대 3개를 골라 주세요. 멘토가 그중 하나로 승인해요.`
        : step === "content"
          ? "주제와 미리 볼 내용을 적어 주면 멘토가 준비해 와요."
          : "신청하면 멘토에게 알림이 가고, 승인 전까지 취소할 수 있어요.";

  const next = async () => {
    const index = STEPS.findIndex((s) => s.value === step);
    if (step === "schedule") update({ duration });
    if (step === "content" && !(await form.trigger())) return;
    const following = STEPS[index + 1];
    if (following) go(following.value);
  };

  const submit = async () => {
    if (!draft.mentorId || !cohortId) return;
    setServerError(null);
    try {
      const created = await create.mutateAsync({
        cohortId,
        mentorId: draft.mentorId,
        topic: draft.topic.trim(),
        detail: draft.detail.trim(),
        desiredTimes: draft.desiredTimes,
        duration,
      });
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
    !gate.blocked && (step === "mentor" ? !!mentor : step === "schedule" ? draft.desiredTimes.length > 0 : true);

  return (
    <div className="flex flex-col gap-6">
      {blocked ? <Alert variant="warning" title={blocked.title} description={blocked.description} /> : null}
      {head.back ? (
        <Link
          to="/mentoring/apply"
          search={head.back.to === "mentor" ? {} : { step: head.back.to }}
          className="inline-flex w-fit items-center gap-1.5 text-body-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft aria-hidden className="size-4" />
          {head.back.label}
        </Link>
      ) : null}
      <Stepper current={step} />
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">{head.title}</h1>
        {subtitle ? <p className="text-body text-muted-foreground">{subtitle}</p> : null}
      </div>
      {gate.blocked && gate.blocked !== "no_time" ? null : step === "mentor" ? (
        ready ? (
          <MentorStep
            cohortId={cohortId}
            selected={draft.mentorId}
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
      {step !== "confirm" && (!gate.blocked || gate.blocked === "no_time") ? (
        <div className="flex justify-end">
          <Button className="w-full md:w-auto" disabled={!canNext} onClick={() => void next()}>
            다음: {STEPS[STEPS.findIndex((s) => s.value === step) + 1]?.label}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
