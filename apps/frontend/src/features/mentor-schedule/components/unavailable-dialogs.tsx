import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarRange, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Controller, useForm, useWatch, type UseFormReturn } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { PanelActions, PanelHead, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { formatKst, formatKstDay } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { useDeleteUnavailable, useSaveUnavailable, type ScheduleChange, type UnavailableInput } from "../api";
import { personalLabel } from "../calendar";
import {
  bodyOf,
  CATEGORY_MAX_LENGTH,
  CATEGORY_SUGGESTIONS,
  crossesMidnight,
  emptyForm,
  formOf,
  isLocked,
  REASON_MAX_LENGTH,
  summaryOf,
  TIME_OPTIONS,
  unavailableSchema,
  type UnavailableForm,
} from "../form";
import { dayStartMs, periodLabel, repeatLabel, type UnavailablePeriod } from "../schedule";
import { useScheduleScope } from "../scope";

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

const HELP = {
  time: "30분 단위로 골라요. 종료가 시작보다 이르면 다음 날로 넘어가요(자정을 넘는 시간).",
  range: "반복 종료를 비우면 계속 반복해요.",
  days: "여러 날 쉬면 마지막 날을 골라요.",
  conflict: "등록한 시간에는 수강생이 신청할 수 없어요. 이미 받은 신청·세션과 겹치면 저장 전에 알려 드려요.",
};

const CHIP =
  "h-8 rounded-full border px-3.5 text-label outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring";
const CHIP_ON = "border-primary/50 bg-sidebar-accent text-body-strong text-sidebar-accent-foreground";
const CHIP_OFF = "border-border text-foreground hover:bg-muted";

type Form = UseFormReturn<UnavailableForm>;

/** 패널 상태: 상세 · 추가 · 수정 (F89) */
export type PanelState =
  | { mode: "view"; period: UnavailablePeriod }
  | { mode: "edit"; period: UnavailablePeriod; from: "view" | "list" }
  | { mode: "add"; day: string };

/**
 * 개인 일정 슬라이드 패널 (Figma `일정 · 데스크톱 (개인 일정 상세·추가 패널)`, F68·F89).
 * 상세는 섹션 '일정'·'기타' 조회 + 머리 [수정][삭제], 추가·수정은 같은 섹션에 입력 + [취소][저장].
 * 휴대폰은 전체 폭. 이미 시작한 '한 번'과 고칠 권한이 없으면 조회만.
 */
export function UnavailablePanel({
  state,
  now,
  onChange,
  onDelete,
}: {
  state: PanelState | null;
  now: number;
  onChange: (state: PanelState | null) => void;
  onDelete: (period: UnavailablePeriod) => void;
}) {
  const close = () => onChange(null);
  return (
    <Sheet open={!!state} onOpenChange={(open) => (open ? undefined : close())}>
      <SheetContent aria-describedby={undefined} className="w-120 max-md:w-full">
        {state?.mode === "view" ? (
          <PeriodView
            period={state.period}
            now={now}
            onEdit={() => onChange({ mode: "edit", period: state.period, from: "view" })}
            onDelete={() => onDelete(state.period)}
            onClose={close}
          />
        ) : state ? (
          <PeriodEditor
            key={state.mode === "edit" ? state.period.id : "add"}
            period={state.mode === "edit" ? state.period : null}
            defaultDay={state.mode === "add" ? state.day : ""}
            onCancel={() =>
              state.mode === "edit" && state.from === "view"
                ? onChange({ mode: "view", period: state.period })
                : close()
            }
            onSaved={close}
            onClose={close}
          />
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function dot(key: string): string {
  return formatKst(dayStartMs(key), "yyyy.MM.dd");
}

function PeriodView({
  period: p,
  now,
  onEdit,
  onDelete,
  onClose,
}: {
  period: UnavailablePeriod;
  now: number;
  onEdit: () => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const scope = useScheduleScope();
  const v = formOf(p);
  const editable = !scope.readOnly && !isLocked(p, now);
  const days = [...p.weekdays]
    .sort()
    .map((d) => WEEKDAYS[d - 1])
    .join("·");
  const time = p.all_day
    ? "하루 종일"
    : summaryOf({ ...v, repeat: "ONCE" })
        .split(" ")
        .slice(1)
        .join(" ");
  return (
    <>
      <PanelHead
        title={p.category ?? "개인 일정"}
        description={periodLabel(p)}
        badges={<Badge variant="outline">{repeatLabel(p)}</Badge>}
        actions={editable ? <PanelActions onEdit={onEdit} onDelete={onDelete} /> : null}
        onClose={onClose}
      />
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6 max-md:p-4">
        <PanelSection title="일정">
          <PanelRow label="반복">
            {p.repeat === "WEEKLY" ? `매주 ${days}` : p.repeat === "DAILY" ? "매일" : "한 번"}
          </PanelRow>
          <PanelRow label="시간">{time}</PanelRow>
          <PanelRow label={p.repeat === "ONCE" ? "날짜" : "적용 기간"}>
            {p.repeat === "ONCE"
              ? v.endDate && v.endDate !== v.startDate
                ? `${dot(v.startDate)} ~ ${dot(v.endDate)}`
                : dot(v.startDate)
              : `${dot(v.startDate)} ~ ${p.repeat_until ? dot(p.repeat_until) : "계속"}`}
          </PanelRow>
        </PanelSection>
        <PanelSection title="기타">
          <PanelRow label="분류">{p.category ?? "—"}</PanelRow>
          <PanelRow label="메모">{p.reason ?? "—"}</PanelRow>
        </PanelSection>
        {isLocked(p, now) ? (
          <p className="text-caption text-muted-foreground">이미 시작한 한 번 일정은 바꿀 수 없어요.</p>
        ) : null}
      </div>
    </>
  );
}

function PeriodEditor({
  period,
  defaultDay,
  onCancel,
  onSaved,
  onClose,
}: {
  period: UnavailablePeriod | null;
  defaultDay: string;
  onCancel: () => void;
  onSaved: () => void;
  onClose: () => void;
}) {
  const scope = useScheduleScope();
  const save = useSaveUnavailable(period?.id ?? null, scope.mentorId);
  const [serverError, setServerError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ body: UnavailableInput; change: ScheduleChange } | null>(null);
  const form = useForm<UnavailableForm>({
    resolver: zodResolver(unavailableSchema),
    defaultValues: period ? formOf(period) : emptyForm(defaultDay),
  });
  const values = useWatch({ control: form.control }) as UnavailableForm;
  const errors = form.formState.errors;
  const once = values.repeat === "ONCE";
  const allDay = once && values.allDay;

  const send = async (body: UnavailableInput, confirm: boolean) => {
    setServerError(null);
    try {
      const change = await save.mutateAsync({ body, confirm });
      if (!change.applied) {
        setPreview({ body, change });
        return;
      }
      setPreview(null);
      toast.success(
        change.conflicts.length > 0
          ? `저장했어요. 겹친 일정 ${change.conflicts.length}건을 정리했어요`
          : period
            ? "개인 일정을 고쳤어요"
            : "개인 일정을 추가했어요",
      );
      onSaved();
    } catch (e) {
      const code = e instanceof ApiError ? e.code : undefined;
      setPreview(null);
      setServerError((code && ERROR_MESSAGES[code]) ?? FALLBACK);
    }
  };
  const onSubmit = form.handleSubmit((v) => send(bodyOf(v), false));
  const title = period ? (period.category ?? "개인 일정") : "개인 일정 추가";

  return (
    <>
      <PanelHead
        title={title}
        description={period ? periodLabel(period) : "신청을 받지 않을 시간을 등록해요"}
        badges={period ? <Badge variant="warning">수정 중</Badge> : null}
        onClose={onClose}
      />
      <form
        aria-label={period ? "개인 일정 수정" : "개인 일정 추가"}
        noValidate
        onSubmit={(e) => void onSubmit(e)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6 max-md:p-4">
          <PanelSection title="일정">
            <PanelRow label="반복" help={HELP.conflict}>
              <Controller
                control={form.control}
                name="repeat"
                render={({ field }) => (
                  <Segmented label="반복" value={field.value} onChange={field.onChange} options={REPEATS} />
                )}
              />
            </PanelRow>
            {values.repeat === "WEEKLY" ? (
              <PanelRow label="요일">
                <Controller
                  control={form.control}
                  name="weekdays"
                  render={({ field }) => (
                    <div className="flex flex-wrap gap-1">
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
                              "size-8 rounded-full border text-label outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
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
                <FieldError message={errors.weekdays?.message} />
              </PanelRow>
            ) : null}
            <PanelRow label="시간" help={HELP.time} top>
              <TimeFields form={form} values={values} allDay={allDay} once={once} />
            </PanelRow>
            <RangeFields form={form} once={once} allDay={allDay} />
          </PanelSection>
          <PanelSection title="기타">
            <PanelRow label="분류" top>
              <CategoryField form={form} category={values.category} />
            </PanelRow>
            <PanelRow label="메모" htmlFor="unavailable-reason">
              <Input
                id="unavailable-reason"
                maxLength={REASON_MAX_LENGTH}
                placeholder="나만 보는 메모예요"
                {...form.register("reason")}
              />
              <FieldError message={errors.reason?.message} />
            </PanelRow>
          </PanelSection>
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
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-6 py-3 max-md:px-4">
          <Button type="button" variant="outline" className="max-md:flex-1" onClick={onCancel}>
            취소
          </Button>
          <Button type="submit" className="max-md:flex-1" disabled={save.isPending}>
            저장
          </Button>
        </div>
      </form>
      <ConflictDialog
        change={preview?.change ?? null}
        pending={save.isPending}
        onBack={() => setPreview(null)}
        onConfirm={() => preview && void send(preview.body, true)}
      />
    </>
  );
}

function FieldError({ message }: { message?: string }) {
  return message ? <p className="mt-1 text-caption font-normal text-destructive-text">{message}</p> : null;
}

function TimeSelect({ form, name, label }: { form: Form; name: "startTime" | "endTime"; label: string }) {
  return (
    <Controller
      control={form.control}
      name={name}
      render={({ field }) => (
        <Select value={field.value} onValueChange={field.onChange}>
          <SelectTrigger aria-label={label} className="w-24">
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

/** 시작 ~ 종료 (30분 단위). 종료가 시작보다 이르면 다음 날. 한 번은 '하루 종일' 스위치 */
function TimeFields({
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
  return (
    <div className="flex flex-col gap-2 font-normal">
      {allDay ? (
        <span className="flex min-h-9 items-center text-body text-muted-foreground">그날 전체</span>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
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
            <label className="inline-flex w-fit items-center gap-2 text-body text-foreground">
              <Switch checked={field.value} onCheckedChange={field.onChange} aria-label="하루 종일" />
              하루 종일
            </label>
          )}
        />
      ) : null}
      <FieldError message={form.formState.errors.endTime?.message} />
    </div>
  );
}

/** 적용 기간: 반복은 시작일 ~ 반복 종료(비우면 계속), 한 번은 날짜(하루 종일이면 마지막 날까지) */
function RangeFields({ form, once, allDay }: { form: Form; once: boolean; allDay: boolean }) {
  const errors = form.formState.errors;
  if (once && !allDay)
    return (
      <PanelRow label="날짜" htmlFor="unavailable-start">
        <Input id="unavailable-start" type="date" {...form.register("startDate")} />
        <FieldError message={errors.startDate?.message} />
      </PanelRow>
    );
  const [firstLabel, lastLabel, lastName] = once
    ? (["첫 날", "마지막 날 (선택)", "endDate"] as const)
    : (["시작일", "반복 종료 (선택)", "repeatUntil"] as const);
  return (
    <PanelRow label={once ? "날짜" : "적용 기간"} help={once ? HELP.days : HELP.range}>
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2">
        <Input type="date" aria-label={firstLabel} {...form.register("startDate")} />
        <span aria-hidden className="text-muted-foreground">
          ~
        </span>
        <Input type="date" aria-label={lastLabel} {...form.register(lastName)} />
      </div>
      <FieldError message={errors.startDate?.message ?? errors[lastName]?.message} />
    </PanelRow>
  );
}

/** 분류: 칩만 고른다. '기타'를 고르면 직접 적는다 (F88) */
function CategoryField({ form, category }: { form: Form; category: string }) {
  const suggested = (CATEGORY_SUGGESTIONS as readonly string[]).includes(category);
  const [otherOn, setOtherOn] = useState(false);
  const other = otherOn || (category !== "" && !suggested);
  const pick = (value: string) => {
    setOtherOn(false);
    form.setValue("category", category === value ? "" : value, { shouldDirty: true });
  };
  return (
    <div className="flex flex-col gap-2 font-normal">
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
      <FieldError message={form.formState.errors.category?.message} />
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
  onDeleted,
}: {
  period: UnavailablePeriod | null;
  onClose: () => void;
  onDeleted?: () => void;
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
      onDeleted?.();
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
          {period ? `${personalLabel(period)} · ${periodLabel(period)}` : ""}
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
