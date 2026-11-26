import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarRange, TriangleAlert } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Controller, useForm, useWatch, type UseFormReturn } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { HelpTip } from "@/components/ui/help-tip";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { formatKstDay, formatKst } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { useDeleteUnavailable, useSaveUnavailable, type ScheduleChange, type UnavailableInput } from "../api";
import { useScheduleScope } from "../scope";
import {
  bodyOf,
  CATEGORY_MAX_LENGTH,
  CATEGORY_SUGGESTIONS,
  crossesMidnight,
  emptyForm,
  formOf,
  REASON_MAX_LENGTH,
  summaryOf,
  TIME_OPTIONS,
  unavailableSchema,
  type UnavailableForm,
} from "../form";
import { periodLabel, type UnavailablePeriod } from "../schedule";

const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];
const REPEATS = [
  { value: "ONCE", label: "한 번" },
  { value: "DAILY", label: "매일" },
  { value: "WEEKLY", label: "매주" },
] as const;
const OTHER = "기타";

const ERROR_MESSAGES: Record<string, string> = {
  unavailable_period_started: "이미 시작한 한 번 개인 일정은 바꿀 수 없어요.",
  invalid_unavailable_range: "시작과 종료를 다시 확인해 주세요. 한 번에 24시간까지 등록할 수 있어요.",
  invalid_slot_boundary: "시각은 정각이나 30분으로 골라 주세요.",
  invalid_repeat_rule: "반복 설정을 다시 확인해 주세요.",
  mentor_inactive: "비활성 멘토는 일정을 바꿀 수 없어요. 운영진에게 문의해 주세요.",
  unavailable_period_not_found: "이미 지워진 개인 일정이에요. 화면을 새로 불러와 주세요.",
};
const FALLBACK = "저장하지 못했어요. 잠시 후 다시 시도해 주세요.";

/** 휴대폰은 전체 화면 창, 그 밖은 가운데 창 (F53) */
const SHEET =
  "flex max-h-[90dvh] max-w-140 flex-col gap-5 overflow-y-auto p-6 max-md:inset-0 max-md:top-0 max-md:h-dvh max-md:max-h-none max-md:max-w-none max-md:translate-y-0 max-md:rounded-none max-md:border-0 max-md:p-4";

const CHIP =
  "h-8 rounded-full border px-3.5 text-label outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring";
const CHIP_ON = "border-primary/50 bg-sidebar-accent text-body-strong text-sidebar-accent-foreground";
const CHIP_OFF = "border-border text-foreground hover:bg-muted";

type Form = UseFormReturn<UnavailableForm>;

/**
 * 불가 시간 추가·수정 창 (Figma `불가 시간 추가 · 데스크톱 (F88 개편)`, F53·F88·A37).
 * 질문 순서: 반복 → 요일 → 시간 → 적용 기간 → 분류 → 메모, 아래에 요약 한 줄. 충돌이면 확인 창을 거친다.
 */
export function UnavailableDialog({
  open,
  onOpenChange,
  period,
  defaultDay,
  defaultTime,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  period: UnavailablePeriod | null;
  defaultDay: string;
  /** 시간표 빈 칸을 눌러 열면 그 시각 (F88) */
  defaultTime?: string;
}) {
  const scope = useScheduleScope();
  const save = useSaveUnavailable(period?.id ?? null, scope.mentorId);
  const [serverError, setServerError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ body: UnavailableInput; change: ScheduleChange } | null>(null);
  const form = useForm<UnavailableForm>({
    resolver: zodResolver(unavailableSchema),
    values: period ? formOf(period) : emptyForm(defaultDay, defaultTime),
  });
  const values = useWatch({ control: form.control }) as UnavailableForm;
  const errors = form.formState.errors;
  const once = values.repeat === "ONCE";
  const allDay = once && values.allDay;

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
            ? "개인 일정을 고쳤어요"
            : "개인 일정을 추가했어요",
      );
      close();
    } catch (e) {
      const code = e instanceof ApiError ? e.code : undefined;
      setPreview(null);
      setServerError((code && ERROR_MESSAGES[code]) ?? FALLBACK);
    }
  };

  const onSubmit = form.handleSubmit((v) => send(bodyOf(v), false));

  return (
    <>
      <Dialog open={open && !preview} onOpenChange={(next) => (next ? onOpenChange(true) : close())}>
        <DialogContent className={SHEET}>
          <div className="flex items-center gap-1.5 pr-8">
            <DialogTitle className="text-h2 text-foreground">
              {period ? "개인 일정 수정" : "개인 일정 추가"}
            </DialogTitle>
            <HelpTip label="개인 일정">
              등록한 시간에는 수강생이 신청할 수 없어요. 이미 받은 신청·세션과 겹치면 저장 전에 알려 드려요.
            </HelpTip>
          </div>
          <DialogDescription className="sr-only">신청을 받지 않을 시간을 등록해요</DialogDescription>
          <form
            id="unavailable-form"
            onSubmit={(e) => void onSubmit(e)}
            className="flex flex-1 flex-col gap-5"
            noValidate
          >
            <Question label="반복">
              <Controller
                control={form.control}
                name="repeat"
                render={({ field }) => (
                  <Segmented label="반복" value={field.value} onChange={field.onChange} options={REPEATS} />
                )}
              />
            </Question>
            {values.repeat === "WEEKLY" ? (
              <Question label="요일" error={errors.weekdays?.message}>
                <Controller
                  control={form.control}
                  name="weekdays"
                  render={({ field }) => (
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
                              "size-10 rounded-full border text-label outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring max-md:size-auto max-md:aspect-square max-md:flex-1",
                              on ? CHIP_ON : cn(CHIP_OFF, day > 5 && "text-muted-foreground"),
                            )}
                          >
                            {label}
                          </button>
                        );
                      })}
                    </div>
                  )}
                />
              </Question>
            ) : null}
            <TimeQuestion form={form} values={values} allDay={allDay} once={once} />
            <PeriodQuestion form={form} once={once} allDay={allDay} />
            <CategoryQuestion form={form} category={values.category} />
            <Question
              label="메모 (선택)"
              htmlFor="unavailable-reason"
              error={errors.reason?.message}
              aside={`${values.reason.length} / ${REASON_MAX_LENGTH}`}
            >
              <Input
                id="unavailable-reason"
                maxLength={REASON_MAX_LENGTH}
                placeholder="나만 보는 메모예요"
                {...form.register("reason")}
              />
            </Question>
            <p
              aria-live="polite"
              className="flex items-center gap-2 rounded-lg bg-sidebar-accent px-3.5 py-2.5 text-body-strong text-sidebar-accent-foreground"
            >
              <CalendarRange aria-hidden className="size-4 shrink-0" />
              <span>
                {values.category.trim() ? `${values.category.trim()} · ` : ""}
                {summaryOf(values)}
              </span>
            </p>
            {serverError ? <Alert variant="error" title={serverError} /> : null}
            <div className="mt-auto flex justify-end gap-2 max-md:sticky max-md:bottom-0 max-md:bg-popover max-md:pt-2">
              <Button type="button" variant="outline" className="max-md:flex-1" onClick={close}>
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

/** 질문 한 칸: 라벨(+ 오른쪽 보조) · 입력 · 오류 */
function Question({
  label,
  htmlFor,
  help,
  aside,
  error,
  children,
}: {
  label: string;
  htmlFor?: string;
  help?: string;
  aside?: ReactNode;
  error?: string;
  children: ReactNode;
}) {
  const Label = htmlFor ? "label" : "span";
  return (
    <div role={htmlFor ? undefined : "group"} aria-label={htmlFor ? undefined : label} className="flex flex-col gap-2">
      <div className="flex items-center gap-1.5">
        <Label htmlFor={htmlFor} className="text-label text-foreground">
          {label}
        </Label>
        {help ? <HelpTip label={label}>{help}</HelpTip> : null}
        {aside ? <span className="ml-auto text-caption text-muted-foreground">{aside}</span> : null}
      </div>
      {children}
      {error ? <p className="text-caption text-destructive-text">{error}</p> : null}
    </div>
  );
}

function TimeSelect({ form, name, label }: { form: Form; name: "startTime" | "endTime"; label: string }) {
  return (
    <Controller
      control={form.control}
      name={name}
      render={({ field }) => (
        <Select value={field.value} onValueChange={field.onChange}>
          <SelectTrigger aria-label={label} className="w-28">
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
      )}
    />
  );
}

/** 시간: 시작 ~ 종료 (30분 단위). 종료가 시작보다 이르면 다음 날. 한 번은 '하루 종일' 스위치 */
function TimeQuestion({
  form,
  values,
  allDay,
  once,
}: {
  form: Form;
  values: UnavailableForm;
  allDay: boolean;
  once: boolean;
}) {
  const errors = form.formState.errors;
  return (
    <Question
      label="시간"
      help="30분 단위로 골라요. 종료가 시작보다 이르면 다음 날로 넘어가요(자정을 넘는 시간)."
      error={errors.endTime?.message}
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {allDay ? (
          <span className="text-body text-muted-foreground">그날 전체</span>
        ) : (
          <div className="flex items-center gap-2">
            <TimeSelect form={form} name="startTime" label="시작 시각" />
            <span aria-hidden className="text-muted-foreground">
              ~
            </span>
            <TimeSelect form={form} name="endTime" label="종료 시각" />
            {crossesMidnight(values) && values.endTime !== "00:00" ? <Badge variant="outline">다음 날</Badge> : null}
          </div>
        )}
        {once ? (
          <Controller
            control={form.control}
            name="allDay"
            render={({ field }) => (
              <label className="ml-auto inline-flex items-center gap-2 text-body text-foreground">
                <Switch checked={field.value} onCheckedChange={field.onChange} aria-label="하루 종일" />
                하루 종일
              </label>
            )}
          />
        ) : null}
      </div>
    </Question>
  );
}

/** 적용 기간: 반복은 시작일 ~ 반복 종료(비우면 계속), 한 번은 날짜(하루 종일이면 마지막 날까지) */
function PeriodQuestion({ form, once, allDay }: { form: Form; once: boolean; allDay: boolean }) {
  const errors = form.formState.errors;
  if (once && !allDay)
    return (
      <Question label="날짜" htmlFor="unavailable-start" error={errors.startDate?.message}>
        <Input id="unavailable-start" type="date" className="md:w-48" {...form.register("startDate")} />
      </Question>
    );
  const [firstLabel, lastLabel, lastName] = once
    ? (["첫 날", "마지막 날 (선택)", "endDate"] as const)
    : (["시작일", "반복 종료 (선택)", "repeatUntil"] as const);
  return (
    <Question
      label={once ? "날짜" : "적용 기간"}
      help={once ? "여러 날 쉬면 마지막 날을 골라요." : "반복 종료를 비우면 계속 반복해요."}
      error={errors.startDate?.message ?? errors[lastName]?.message}
    >
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2">
        <Input type="date" aria-label={firstLabel} {...form.register("startDate")} />
        <span aria-hidden className="text-muted-foreground">
          ~
        </span>
        <Input type="date" aria-label={lastLabel} {...form.register(lastName)} />
      </div>
    </Question>
  );
}

/** 분류: 칩만 고른다. '기타'를 고르면 직접 적는다 (F88) */
function CategoryQuestion({ form, category }: { form: Form; category: string }) {
  const suggested = (CATEGORY_SUGGESTIONS as readonly string[]).includes(category);
  const [otherOn, setOtherOn] = useState(false);
  const other = otherOn || (category !== "" && !suggested);
  const pick = (value: string) => {
    setOtherOn(false);
    form.setValue("category", category === value ? "" : value, { shouldDirty: true });
  };
  return (
    <Question label="분류 (선택)" error={form.formState.errors.category?.message}>
      <div className="flex flex-wrap gap-1.5">
        {CATEGORY_SUGGESTIONS.map((c) => (
          <button
            key={c}
            type="button"
            aria-pressed={category === c}
            onClick={() => pick(c)}
            className={cn(CHIP, category === c ? CHIP_ON : CHIP_OFF)}
          >
            {c}
          </button>
        ))}
        <button
          type="button"
          aria-pressed={other}
          onClick={() => {
            if (other) {
              setOtherOn(false);
              form.setValue("category", "", { shouldDirty: true });
            } else {
              setOtherOn(true);
              if (suggested) form.setValue("category", "", { shouldDirty: true });
            }
          }}
          className={cn(CHIP, other ? CHIP_ON : CHIP_OFF)}
        >
          {OTHER}
        </button>
      </div>
      {other ? (
        <Input
          aria-label="분류 직접 입력"
          autoFocus={otherOn}
          maxLength={CATEGORY_MAX_LENGTH}
          placeholder="예: 스터디"
          {...form.register("category")}
        />
      ) : null}
    </Question>
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
      toast.success("개인 일정을 지웠어요");
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
        <DialogTitle className="text-h2 text-foreground">이 개인 일정을 지울까요?</DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          {period ? `${period.category ?? "개인 일정"} · ${periodLabel(period)}` : ""}
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
