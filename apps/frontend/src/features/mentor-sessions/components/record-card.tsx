import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch, type UseFormRegisterReturn } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { Markdown } from "@/components/markdown";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { sessionKeys, type MentoringSession } from "@/features/sessions/api";
import { actualMinutes, cancelNote, plannedMinutes } from "@/features/sessions/labels";
import { formatKst, formatKstDayTime, formatMinutes, toEpochMs } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { useEditRecord, useSubmitRecord } from "../api";
import { RECORD_ERROR_MESSAGES, RECORD_FALLBACK_MESSAGE } from "../messages";
import {
  durationOptions,
  editSchema,
  RECORD_EDIT_DAYS,
  recordSchema,
  SUMMARY_MAX_LENGTH,
  TOPIC_MAX_LENGTH,
  type EditForm,
  type RecordForm,
} from "../schemas";

const DAY_MS = 24 * 60 * 60_000;

/** 세션 기록 카드 (F48): 취소·시작 전·작성·제출 후(수정) 중 하나 */
export function RecordCard({ session, now }: { session: MentoringSession; now: number }) {
  if (session.status === "CANCELED") {
    return (
      <Card title="취소된 세션이에요">
        <p className="text-body text-muted-foreground">{cancelNote(session, false)}</p>
      </Card>
    );
  }
  if (session.recorded_at) return <RecordView session={session} now={now} />;
  if (toEpochMs(session.starts_at) > now) {
    return (
      <Card title="세션 기록">
        <p className="text-body text-muted-foreground">
          {formatKstDayTime(session.starts_at)} 시작 후 기록할 수 있어요. 진행 결과·실제 진행 시간·요약을 적어 주세요.
        </p>
      </Card>
    );
  }
  return <RecordFormCard session={session} />;
}

function Card({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 md:p-6">
      <div className="flex items-center gap-2">
        <h2 className="flex-1 text-h3 text-foreground">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function errorMessage(e: unknown): { code: string | undefined; message: string } {
  const code = e instanceof ApiError ? e.code : undefined;
  return { code, message: (code && RECORD_ERROR_MESSAGES[code]) ?? RECORD_FALLBACK_MESSAGE };
}

/** 기록 작성 (A53·A78) */
function RecordFormCard({ session }: { session: MentoringSession }) {
  const queryClient = useQueryClient();
  const submit = useSubmitRecord(session.id);
  const planned = plannedMinutes(session);
  const actual = actualMinutes(session);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<RecordForm>({
    resolver: zodResolver(recordSchema),
    defaultValues: { status: "COMPLETED", duration: planned, topic: session.topic, summary: "" },
  });
  const [status, duration, summary] = useWatch({ control: form.control, name: ["status", "duration", "summary"] });
  const completed = status === "COMPLETED";
  const diff = completed && duration ? duration - planned : 0;
  const errors = form.formState.errors;

  const onSubmit = form.handleSubmit(async (values) => {
    setServerError(null);
    try {
      await submit.mutateAsync(
        values.status === "COMPLETED"
          ? { status: "COMPLETED", duration: values.duration, topic: values.topic, summary: values.summary }
          : { status: "NO_SHOW", summary: values.summary || null },
      );
      toast.success(values.status === "COMPLETED" ? "기록을 제출했어요" : "노쇼로 기록했어요");
    } catch (e) {
      const { code, message } = errorMessage(e);
      if (code === "session_not_recordable")
        void queryClient.invalidateQueries({ queryKey: sessionKeys.detail(session.id) });
      setServerError(message);
    }
  });

  return (
    <Card title="세션 기록">
      <form onSubmit={(e) => void onSubmit(e)} className="flex flex-col gap-5" noValidate>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-label text-foreground">결과</legend>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            {(
              [
                ["COMPLETED", "진행함"],
                ["NO_SHOW", "노쇼 (수강생이 들어오지 않음)"],
              ] as const
            ).map(([value, label]) => (
              <label key={value} className="inline-flex cursor-pointer items-center gap-2 text-body text-foreground">
                <input type="radio" value={value} className="size-4 accent-primary" {...form.register("status")} />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        {completed ? (
          <>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <span id="record-duration" className="text-label text-foreground">
                  실제 진행 시간
                </span>
                <Select
                  value={String(duration ?? planned)}
                  onValueChange={(v) => form.setValue("duration", Number(v), { shouldValidate: true })}
                >
                  <SelectTrigger aria-labelledby="record-duration">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {durationOptions(planned).map((m) => (
                      <SelectItem key={m} value={String(m)}>
                        {m}분
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {session.actual_started_at && session.actual_ended_at && actual !== null ? (
                <div className="flex flex-col gap-0.5 rounded-lg bg-muted px-3.5 py-2.5">
                  <span className="text-caption text-muted-foreground">Meet 기록 (참고)</span>
                  <span className="text-body-strong text-foreground">
                    {formatKst(session.actual_started_at, "HH:mm")} ~ {formatKst(session.actual_ended_at, "HH:mm")} ·{" "}
                    {actual}분
                  </span>
                </div>
              ) : null}
            </div>
            {diff > 0 ? (
              <Alert
                variant="info"
                title={`신청보다 ${formatMinutes(diff)} 길게 진행했어요`}
                description={`초과한 ${formatMinutes(diff)}은 신청자(팀)의 남은 시간에서 차감돼요. 남은 시간이 모자라면 차감하지 못한 시간은 운영진이 정산할 때 참고해요. 제출 후에는 결과·진행 시간을 바꿀 수 없어요.`}
              />
            ) : diff < 0 ? (
              <Alert
                variant="info"
                title={`신청보다 ${formatMinutes(-diff)} 짧게 진행했어요`}
                description={`차이 ${formatMinutes(-diff)}은 신청자(팀)에게 돌려드려요. 제출 후에는 결과·진행 시간을 바꿀 수 없어요.`}
              />
            ) : null}
            <TopicField register={form.register("topic")} error={errors.topic?.message} />
          </>
        ) : null}
        <MarkdownField
          label={completed ? "요약 (수강생도 봐요)" : "노쇼 사유 (선택, 수강생도 봐요)"}
          value={summary ?? ""}
          register={form.register("summary")}
          error={errors.summary?.message}
          hint={
            completed
              ? "마크다운을 쓸 수 있어요 (제목·목록·체크박스·링크·코드). 주제와 요약은 제출 후 7일까지 고칠 수 있어요."
              : "노쇼로 제출하면 신청한 시간을 모두 돌려드려요. 제출 후에는 바꿀 수 없어요."
          }
        />
        {serverError ? <Alert variant="error" title={serverError} /> : null}
        <div className="flex justify-end">
          <Button type="submit" disabled={submit.isPending} className="max-md:w-full">
            기록 제출
          </Button>
        </div>
      </form>
    </Card>
  );
}

function TopicField({ register, error }: { register: UseFormRegisterReturn; error: string | undefined }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={`record-${register.name}`} className="text-label text-foreground">
        주제
      </label>
      <Input
        id={`record-${register.name}`}
        maxLength={TOPIC_MAX_LENGTH}
        aria-invalid={error ? true : undefined}
        {...register}
      />
      {error ? <p className="text-caption text-destructive-text">{error}</p> : null}
    </div>
  );
}

/** 마크다운 입력: [작성]·[미리보기] 탭과 글자 수 */
function MarkdownField({
  label,
  value,
  register,
  error,
  hint,
}: {
  label: string;
  value: string;
  register: UseFormRegisterReturn;
  error: string | undefined;
  hint: string;
}) {
  const [tab, setTab] = useState<"write" | "preview">("write");
  const id = `record-${register.name}`;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="text-label text-foreground">
          {label}
        </label>
        <div role="tablist" aria-label={`${label} 보기`} className="flex gap-1">
          {(["write", "preview"] as const).map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={cn(
                "h-8 rounded-md px-3 text-label",
                tab === t ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t === "write" ? "작성" : "미리보기"}
            </button>
          ))}
        </div>
      </div>
      <Textarea
        id={id}
        rows={6}
        maxLength={SUMMARY_MAX_LENGTH}
        aria-invalid={error ? true : undefined}
        className={cn(tab === "preview" && "hidden")}
        {...register}
      />
      {tab === "preview" ? (
        <div aria-label="미리보기" className="min-h-36 rounded-md border border-border px-4 py-3">
          {value.trim() ? (
            <Markdown>{value}</Markdown>
          ) : (
            <p className="text-body-sm text-muted-foreground">내용이 없어요</p>
          )}
        </div>
      ) : null}
      <div className="flex items-start justify-between gap-3">
        <p className="text-caption text-muted-foreground">{error ? null : hint}</p>
        <span className="shrink-0 text-caption text-muted-foreground">
          {value.length.toLocaleString()} / {SUMMARY_MAX_LENGTH.toLocaleString()}
        </span>
      </div>
      {error ? <p className="text-caption text-destructive-text">{error}</p> : null}
    </div>
  );
}

/** 제출한 기록 (F48): 주제·요약만 7일까지 같은 카드에서 고친다 */
function RecordView({ session, now }: { session: MentoringSession; now: number }) {
  const [editing, setEditing] = useState(false);
  const recordedAt = session.recorded_at ?? session.starts_at;
  const deadline = toEpochMs(recordedAt) + RECORD_EDIT_DAYS * DAY_MS;
  const editable = now < deadline;
  const completed = session.status === "COMPLETED";
  const result = completed
    ? `진행함 · ${session.record_duration_minutes ?? plannedMinutes(session)}분 (고정)`
    : "노쇼 (고정)";
  const until = `${formatKst(deadline, "MM/dd")}까지`;

  if (editing && completed)
    return <RecordEditCard session={session} result={result} until={until} onDone={() => setEditing(false)} />;
  return (
    <Card
      title="세션 기록"
      action={
        completed ? (
          editable ? (
            <span className="flex items-center gap-2">
              <span className="text-caption text-muted-foreground max-md:hidden">{until} 수정 가능</span>
              <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                <Pencil aria-hidden />
                수정
              </Button>
            </span>
          ) : (
            <span className="text-caption text-muted-foreground">{until} 수정할 수 있었어요</span>
          )
        ) : null
      }
    >
      <dl className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-x-4 gap-y-2 text-body">
        <dt className="text-caption text-muted-foreground">결과</dt>
        <dd className="text-foreground">{result}</dd>
        {completed ? (
          <>
            <dt className="text-caption text-muted-foreground">주제</dt>
            <dd className="text-foreground">{session.topic}</dd>
          </>
        ) : null}
        <dt className="text-caption text-muted-foreground">제출</dt>
        <dd className="text-foreground">{formatKstDayTime(recordedAt)}</dd>
      </dl>
      {session.summary ? (
        <div className="rounded-lg bg-muted px-4 py-3">
          <Markdown>{session.summary}</Markdown>
        </div>
      ) : null}
    </Card>
  );
}

function RecordEditCard({
  session,
  result,
  until,
  onDone,
}: {
  session: MentoringSession;
  result: string;
  until: string;
  onDone: () => void;
}) {
  const edit = useEditRecord(session.id);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<EditForm>({
    resolver: zodResolver(editSchema),
    defaultValues: { topic: session.topic, summary: session.summary ?? "" },
  });
  const summary = useWatch({ control: form.control, name: "summary" });
  const onSubmit = form.handleSubmit(async (values) => {
    setServerError(null);
    try {
      await edit.mutateAsync(values);
      toast.success("기록을 고쳤어요");
      onDone();
    } catch (e) {
      setServerError(errorMessage(e).message);
    }
  });
  return (
    <Card title="세션 기록">
      <form onSubmit={(e) => void onSubmit(e)} className="flex flex-col gap-5" noValidate>
        <p className="text-body-strong text-muted-foreground">
          {result} · {until} 고칠 수 있어요
        </p>
        <TopicField register={form.register("topic")} error={form.formState.errors.topic?.message} />
        <MarkdownField
          label="요약 (수강생도 봐요)"
          value={summary}
          register={form.register("summary")}
          error={form.formState.errors.summary?.message}
          hint="마크다운을 쓸 수 있어요 (제목·목록·체크박스·링크·코드)."
        />
        {serverError ? <Alert variant="error" title={serverError} /> : null}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onDone}>
            취소
          </Button>
          <Button type="submit" disabled={edit.isPending}>
            저장
          </Button>
        </div>
      </form>
    </Card>
  );
}
