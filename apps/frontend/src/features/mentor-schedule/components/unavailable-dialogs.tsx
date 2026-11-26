import { zodResolver } from "@hookform/resolvers/zod";
import { TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { FormField } from "@/components/form-field";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatKstDay, formatKst } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { useDeleteUnavailable, useSaveUnavailable, type ScheduleChange, type UnavailableInput } from "../api";
import { useScheduleScope } from "../scope";
import {
  bodyOf,
  CATEGORY_MAX_LENGTH,
  CATEGORY_SUGGESTIONS,
  emptyForm,
  formOf,
  REASON_MAX_LENGTH,
  TIME_OPTIONS,
  unavailableSchema,
  type UnavailableForm,
} from "../form";
import { periodLabel, type UnavailablePeriod } from "../schedule";

const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];
const REPEATS = [
  ["ONCE", "한 번"],
  ["DAILY", "매일"],
  ["WEEKLY", "매주"],
] as const;

const ERROR_MESSAGES: Record<string, string> = {
  unavailable_period_started: "이미 시작한 한 번 불가 시간은 바꿀 수 없어요.",
  invalid_unavailable_range: "시작과 종료를 다시 확인해 주세요. 한 번에 24시간까지 등록할 수 있어요.",
  invalid_slot_boundary: "시각은 정각이나 30분으로 골라 주세요.",
  invalid_repeat_rule: "반복 설정을 다시 확인해 주세요.",
  mentor_inactive: "비활성 멘토는 일정을 바꿀 수 없어요. 운영진에게 문의해 주세요.",
  unavailable_period_not_found: "이미 지워진 불가 시간이에요. 화면을 새로 불러와 주세요.",
};
const FALLBACK = "저장하지 못했어요. 잠시 후 다시 시도해 주세요.";

/** 휴대폰은 전체 화면 창, 그 밖은 가운데 창 (F53) */
const SHEET =
  "flex max-w-140 flex-col gap-5 p-6 max-md:inset-0 max-md:top-0 max-md:h-dvh max-md:max-h-none max-md:max-w-none max-md:translate-y-0 max-md:rounded-none max-md:border-0 max-md:p-4";

/** 불가 시간 추가·수정 창 (Figma `Modal / 불가 시간 추가`, F53·A37). 충돌이면 확인 창을 거친다 */
export function UnavailableDialog({
  open,
  onOpenChange,
  period,
  defaultDay,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  period: UnavailablePeriod | null;
  defaultDay: string;
}) {
  const scope = useScheduleScope();
  const save = useSaveUnavailable(period?.id ?? null, scope.mentorId);
  const [serverError, setServerError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ body: UnavailableInput; change: ScheduleChange } | null>(null);
  const form = useForm<UnavailableForm>({
    resolver: zodResolver(unavailableSchema),
    values: period ? formOf(period) : emptyForm(defaultDay),
  });
  const [repeat, allDay, category, reason] = useWatch({
    control: form.control,
    name: ["repeat", "allDay", "category", "reason"],
  });
  const errors = form.formState.errors;
  const once = repeat === "ONCE";
  const dayOnly = once && allDay;

  const close = () => {
    setServerError(null);
    setPreview(null);
    onOpenChange(false);
  };

  const send = async (body: UnavailableInput, confirm: boolean) => {
    setServerError(null);
    try {
      const change = await save.mutateAsync({ body, confirm });
      if (!change.applied) {
        setPreview({ body, change });
        return;
      }
      toast.success(
        change.conflicts.length > 0
          ? `저장했어요. 겹친 일정 ${change.conflicts.length}건을 정리했어요`
          : period
            ? "불가 시간을 고쳤어요"
            : "불가 시간을 추가했어요",
      );
      close();
    } catch (e) {
      const code = e instanceof ApiError ? e.code : undefined;
      setPreview(null);
      setServerError((code && ERROR_MESSAGES[code]) ?? FALLBACK);
    }
  };

  const onSubmit = form.handleSubmit((values) => send(bodyOf(values), false));

  return (
    <>
      <Dialog open={open && !preview} onOpenChange={(next) => (next ? onOpenChange(true) : close())}>
        <DialogContent className={SHEET}>
          <DialogTitle className="text-h2 text-foreground">{period ? "불가 시간 수정" : "불가 시간 추가"}</DialogTitle>
          <DialogDescription className="sr-only">신청을 받지 않을 시간을 등록해요</DialogDescription>
          <form
            id="unavailable-form"
            onSubmit={(e) => void onSubmit(e)}
            className="flex flex-1 flex-col gap-5"
            noValidate
          >
            <Controller
              control={form.control}
              name="repeat"
              render={({ field }) => (
                <fieldset className="flex flex-col gap-2">
                  <legend className="mb-2 text-label text-foreground">반복</legend>
                  <div role="radiogroup" aria-label="반복" className="flex gap-1">
                    {REPEATS.map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        role="radio"
                        aria-checked={field.value === value}
                        onClick={() => field.onChange(value)}
                        className={cn(
                          "h-8 rounded-md px-3 text-label outline-none focus-visible:ring-2 focus-visible:ring-ring",
                          field.value === value ? "bg-accent text-accent-foreground" : "text-muted-foreground",
                        )}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </fieldset>
              )}
            />
            {once ? (
              <label className="inline-flex w-fit items-center gap-2 text-body text-foreground">
                <input type="checkbox" className="size-4 accent-primary" {...form.register("allDay")} />
                하루 종일
              </label>
            ) : null}
            {repeat === "WEEKLY" ? (
              <Controller
                control={form.control}
                name="weekdays"
                render={({ field }) => (
                  <fieldset className="flex flex-col gap-2">
                    <legend className="mb-2 text-label text-foreground">요일</legend>
                    <div className="flex gap-1.5">
                      {WEEKDAYS.map((label, i) => {
                        const day = i + 1;
                        const on = field.value.includes(day);
                        return (
                          <button
                            key={label}
                            type="button"
                            aria-pressed={on}
                            onClick={() =>
                              field.onChange(on ? field.value.filter((d) => d !== day) : [...field.value, day])
                            }
                            className={cn(
                              "h-9 flex-1 rounded-md border text-label outline-none focus-visible:ring-2 focus-visible:ring-ring md:w-10 md:flex-none",
                              on
                                ? "border-primary bg-primary text-primary-foreground"
                                : "border-border text-foreground",
                            )}
                          >
                            {label}
                          </button>
                        );
                      })}
                    </div>
                    {errors.weekdays?.message ? (
                      <p className="text-caption text-destructive-text">{errors.weekdays.message}</p>
                    ) : null}
                  </fieldset>
                )}
              />
            ) : null}
            <DateTimeRow form={form} which="start" dayOnly={dayOnly} />
            <DateTimeRow form={form} which="end" dayOnly={dayOnly} />
            {!once ? (
              <FormField label="반복 종료 (선택)" error={errors.repeatUntil?.message}>
                {(field) => <Input type="date" {...field} {...form.register("repeatUntil")} />}
              </FormField>
            ) : null}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
              <div className="flex flex-col gap-2">
                <FormField label="분류" error={errors.category?.message}>
                  {(field) => (
                    <Input
                      {...field}
                      maxLength={CATEGORY_MAX_LENGTH}
                      placeholder="불가 시간"
                      {...form.register("category")}
                    />
                  )}
                </FormField>
                <div className="flex flex-wrap gap-1.5" aria-label="분류 추천">
                  {CATEGORY_SUGGESTIONS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      aria-pressed={category === c}
                      onClick={() => form.setValue("category", c, { shouldDirty: true })}
                      className={cn(
                        "h-8 rounded-md border px-3 text-label outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        category === c
                          ? "border-primary bg-accent text-accent-foreground"
                          : "border-border text-foreground",
                      )}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>
              <FormField
                label="메모 (선택)"
                error={errors.reason?.message}
                helper={`${reason.length} / ${REASON_MAX_LENGTH}`}
              >
                {(field) => <Input {...field} maxLength={REASON_MAX_LENGTH} {...form.register("reason")} />}
              </FormField>
            </div>
            <p className="text-caption text-muted-foreground">
              30분 단위로 고를 수 있고, 종료를 다음 날로 하면 자정을 넘겨요(한 번에 24시간까지). 이미 받은 신청·세션과
              겹치면 저장 전에 알려 드려요.
            </p>
            {serverError ? <Alert variant="error" title={serverError} /> : null}
            <div className="mt-auto flex justify-end gap-2 max-md:sticky max-md:bottom-0 max-md:bg-popover max-md:pt-2">
              <Button type="button" variant="ghost" className="max-md:flex-1" onClick={close}>
                취소
              </Button>
              <Button type="submit" className="max-md:flex-1" disabled={save.isPending}>
                저장
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
      <ConflictDialog
        change={preview?.change ?? null}
        pending={save.isPending}
        onBack={() => setPreview(null)}
        onConfirm={() => preview && void send(preview.body, true)}
      />
    </>
  );
}

function DateTimeRow({
  form,
  which,
  dayOnly,
}: {
  form: ReturnType<typeof useForm<UnavailableForm>>;
  which: "start" | "end";
  dayOnly: boolean;
}) {
  const dateName = which === "start" ? "startDate" : "endDate";
  const timeName = which === "start" ? "startTime" : "endTime";
  const errors = form.formState.errors;
  const dateLabel = dayOnly
    ? which === "start"
      ? "첫 날"
      : "마지막 날"
    : which === "start"
      ? "시작 날짜"
      : "종료 날짜";
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_8rem] gap-3 md:grid-cols-[minmax(0,1fr)_10rem]">
      <FormField label={dateLabel} error={errors[dateName]?.message} className={cn(dayOnly && "col-span-2")}>
        {(field) => <Input type="date" {...field} {...form.register(dateName)} />}
      </FormField>
      {dayOnly ? null : (
        <Controller
          control={form.control}
          name={timeName}
          render={({ field }) => (
            <div className="flex flex-col gap-1.5">
              <span id={`${timeName}-label`} className="text-label text-foreground">
                {which === "start" ? "시작 시각" : "종료 시각"}
              </span>
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger aria-labelledby={`${timeName}-label`}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TIME_OPTIONS.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors[timeName]?.message ? (
                <p className="text-caption text-destructive-text">{errors[timeName]?.message}</p>
              ) : null}
            </div>
          )}
        />
      )}
    </div>
  );
}

/** 충돌 확인 (Figma `Modal / 충돌 확인`, A37·A45·A79) */
function ConflictDialog({
  change,
  pending,
  onBack,
  onConfirm,
}: {
  change: ScheduleChange | null;
  pending: boolean;
  onBack: () => void;
  onConfirm: () => void;
}) {
  const conflicts = change?.conflicts ?? [];
  return (
    <Dialog open={!!change} onOpenChange={(next) => (next ? null : onBack())}>
      <DialogContent className="flex max-w-140 flex-col gap-4 p-6">
        <div className="flex items-center gap-2.5 pr-8">
          <TriangleAlert aria-hidden className="size-5 text-warning-text" />
          <DialogTitle className="text-h2 text-foreground">겹치는 일정이 {conflicts.length}건 있어요</DialogTitle>
        </div>
        <DialogDescription className="text-body text-muted-foreground">
          저장하면 아래 신청은 반려되고, 세션은 취소돼 수강생에게 시간이 모두 돌아가요. 수강생에게는 채팅으로 안내가
          가요.
        </DialogDescription>
        <ul className="flex flex-col gap-2">
          {conflicts.map((c) => (
            <li key={c.target_id} className="flex items-center gap-3 rounded-lg border border-border px-4 py-3">
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="truncate text-body-strong text-foreground">{c.topic}</span>
                <span className="text-caption text-muted-foreground">
                  {c.requester_label} · {formatKstDay(c.starts_at)} {formatKst(c.starts_at, "HH:mm")}{" "}
                  {c.kind === "REQUEST" ? "희망" : "세션"}
                </span>
              </span>
              <Badge variant={c.kind === "REQUEST" ? "warning" : "destructive"}>
                {c.kind === "REQUEST" ? "대기 신청 → 반려" : "승인 세션 → 취소·환불"}
              </Badge>
            </li>
          ))}
        </ul>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onBack}>
            돌아가기
          </Button>
          <Button variant="destructive" disabled={pending} onClick={onConfirm}>
            그래도 저장
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** 삭제 확인 (F53) */
export function DeleteUnavailableDialog({
  period,
  onClose,
}: {
  period: UnavailablePeriod | null;
  onClose: () => void;
}) {
  const scope = useScheduleScope();
  const remove = useDeleteUnavailable(scope.mentorId);
  const [error, setError] = useState<string | null>(null);
  const onDelete = async () => {
    if (!period) return;
    setError(null);
    try {
      await remove.mutateAsync(period.id);
      toast.success("불가 시간을 지웠어요");
      onClose();
    } catch (e) {
      const code = e instanceof ApiError ? e.code : undefined;
      setError((code && ERROR_MESSAGES[code]) ?? "지우지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  };
  return (
    <Dialog
      open={!!period}
      onOpenChange={(next) => {
        if (!next) {
          setError(null);
          onClose();
        }
      }}
    >
      <DialogContent className="flex max-w-110 flex-col gap-4 p-6">
        <DialogTitle className="text-h2 text-foreground">이 불가 시간을 지울까요?</DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          {period ? `${period.category ?? "불가 시간"} · ${periodLabel(period)}` : ""}
          <br />
          지우면 이 시간에도 수강생이 신청할 수 있어요.
        </DialogDescription>
        {error ? <Alert variant="error" title={error} /> : null}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            돌아가기
          </Button>
          <Button variant="destructive" disabled={remove.isPending} onClick={() => void onDelete()}>
            지우기
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
