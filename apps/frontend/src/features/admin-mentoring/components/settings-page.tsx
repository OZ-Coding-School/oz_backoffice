import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Link, useBlocker } from "@tanstack/react-router";
import {
  CalendarClock,
  CalendarOff,
  Check,
  CircleCheck,
  Clock,
  Hourglass,
  ListChecks,
  Moon,
  Plus,
  Sparkles,
  Sun,
  Timer,
  UserRound,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Controller, useForm, useWatch, type Control, type UseFormReturn } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/error-state";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/ui/help-tip";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { cohortSettingsQuery } from "@/features/admin-academy/api";
import { DiscardDialog } from "@/features/admin-org/components/shared";
import { hasPermissionIn, staffAccessQuery } from "@/features/staff/api";
import { formatKst } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { blockTimesQuery, useSaveSettings, type BlockTime, type MentoringSettings } from "../api";
import { END_TIMES, settingsBody, settingsForm, settingsSchema, START_TIMES, type SettingsForm } from "../form";
import { BlockTimeSheet, type BlockSheetState } from "./block-time-sheet";

const FORM_ID = "mentoring-settings-form";

const HELP = {
  blocks:
    "수업 시간처럼 신청을 막을 시간이에요. 평일(월~금)에만 적용되고 주말·공휴일은 빼요. 등록 전 신청·세션에는 영향이 없어요.",
  weekend: "토·일과 공휴일에 적용돼요. 공휴일은 설정 > 공휴일에서 관리해요.",
};

const ERROR_MESSAGES: Record<string, string> = {
  mentoring_mode_required: "1:1과 팀 멘토링 중 하나 이상을 허용해 주세요.",
  invalid_allowed_duration: "진행 단위는 30분 또는 60분이에요.",
  invalid_min_lead_hours: "신청 마감은 6·12·24시간 중에서 골라 주세요.",
  invalid_max_pending_requests: "대기 신청 수는 1~3건이에요.",
  invalid_default_minutes: "기본 지급 시간은 시간 단위로 적어 주세요.",
  invalid_operating_hours: "운영시간을 다시 확인해 주세요.",
};

/** 멘토링 설정 (Figma `멘토링 설정 (FE-19a)`, F90·A34·A37). 기본 규칙·운영시간은 아래 저장 막대, 금지 시간대는 패널 */
export function SettingsPage({ cohortId }: { cohortId: string }) {
  const access = useQuery(staffAccessQuery);
  const settings = useQuery(cohortSettingsQuery(cohortId));
  const cohort = access.data?.cohorts.find((c) => c.id === cohortId);
  const canManage = !!access.data && !!cohort && hasPermissionIn(access.data, "mentoring.settings.manage", cohort);
  const title = cohort ? `${cohort.bootcamp_name} ${cohort.cohort_number}기` : "";

  if (settings.isPending)
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  if (settings.isError) return <ErrorState onRetry={() => void settings.refetch()} />;
  return <SettingsForm cohortId={cohortId} title={title} settings={settings.data} canManage={canManage} />;
}

function SettingsForm({
  cohortId,
  title,
  settings,
  canManage,
}: {
  cohortId: string;
  title: string;
  settings: MentoringSettings | null;
  canManage: boolean;
}) {
  const save = useSaveSettings(cohortId);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<SettingsForm>({ resolver: zodResolver(settingsSchema), defaultValues: settingsForm(settings) });
  const values = useWatch({ control: form.control }) as SettingsForm;
  const dirty = form.formState.isDirty;
  // 아직 저장하지 않은 기수는 기본값 그대로도 저장할 수 있다
  const canSave = canManage && (dirty || !settings) && !save.isPending;
  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !save.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      const saved = await save.mutateAsync(settingsBody(v));
      form.reset(settingsForm(saved));
      toast.success("멘토링 설정을 저장했어요");
    } catch (e) {
      const code = e instanceof ApiError ? e.code : undefined;
      setError((code && ERROR_MESSAGES[code]) ?? "저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  });

  return (
    <div className={cn("flex flex-col gap-6", canManage && (dirty || !settings) && "pb-4")}>
      <header className="flex flex-col gap-2">
        <h1 className="text-h1 text-foreground">멘토링 설정</h1>
        <div className="flex flex-wrap items-center gap-2 text-body-sm text-muted-foreground">
          <span className="rounded-full bg-sidebar-accent px-2.5 py-0.5 text-caption-strong text-sidebar-accent-foreground">
            {title}
          </span>
          {settings?.updated_at ? (
            <span className="inline-flex items-center gap-1">
              <CircleCheck aria-hidden className="size-3.5 text-success-text" />
              마지막 저장 {formatKst(settings.updated_at, "M월 d일 HH:mm")}
            </span>
          ) : (
            <span>아직 저장하지 않았어요</span>
          )}
        </div>
      </header>
      {!settings ? (
        <Alert
          title="아직 저장하지 않은 기수예요"
          description="기본값을 확인하고 저장하면 이 기수에서 멘토링 신청을 받을 수 있어요."
        />
      ) : null}
      {error ? <Alert variant="error" title={error} /> : null}

      <div className="grid grid-cols-[minmax(0,1fr)_22rem] items-start gap-6">
        {/* 금지 시간대 패널의 폼이 이 폼으로 제출되지 않게 폼은 왼쪽 열만 감싼다 */}
        <form id={FORM_ID} aria-label="멘토링 설정" noValidate onSubmit={(e) => void onSubmit(e)}>
          <fieldset disabled={!canManage} className="flex min-w-0 flex-col gap-6">
            <Section icon={ListChecks} title="기본 규칙" description="수강생이 멘토링을 신청하는 방법이에요.">
              <ModeRow control={form.control} error={form.formState.errors.allow1on1?.message} />
              <Rules form={form} />
            </Section>
            <Section icon={Clock} title="운영시간" description="수강생은 이 시간 안에서만 신청할 수 있어요.">
              <HoursRow
                form={form}
                icon={Sun}
                label="평일"
                sub="월~금"
                on="weekdayOn"
                start="weekdayStart"
                end="weekdayEnd"
              />
              <HoursRow
                form={form}
                icon={Moon}
                label="주말·공휴일"
                sub="토·일·공휴일"
                help={HELP.weekend}
                on="weekendOn"
                start="weekendStart"
                end="weekendEnd"
              />
            </Section>
          </fieldset>
        </form>
        <div className="sticky top-20 flex flex-col gap-6">
          <Summary values={values} />
          <BlockTimes cohortId={cohortId} title={title} canManage={canManage} />
        </div>
      </div>

      {/* 바뀐 것이 있거나 처음 저장할 때만 아래에 떠오른다 */}
      {canManage && (dirty || !settings) ? (
        <SaveBar dirty={dirty} canSave={canSave} pending={save.isPending} onReset={() => form.reset()} />
      ) : null}
      <DiscardDialog blocker={blocker} />
    </div>
  );
}

/** 카드: 아이콘 배지 + 제목·설명, 아래 설정 줄을 구분선으로 */
function Section({
  icon: Icon,
  title,
  description,
  help,
  action,
  children,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  help?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section aria-label={title} className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
      <div className="flex items-center gap-3 px-6 pt-5 pb-4">
        <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-sidebar-accent text-sidebar-accent-foreground">
          <Icon aria-hidden className="size-4.5" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col">
          <h2 className="flex items-center gap-1.5 text-h3 text-foreground">
            {title}
            {help ? <HelpTip label={title}>{help}</HelpTip> : null}
          </h2>
          <p className="text-body-sm text-muted-foreground">{description}</p>
        </div>
        {action}
      </div>
      <div className="flex flex-col divide-y divide-border border-t border-border">{children}</div>
    </section>
  );
}

/** 설정 한 줄: 왼쪽 이름·짧은 설명 | 오른쪽 조작 */
function SettingRow({
  title,
  description,
  error,
  children,
}: {
  title: string;
  description: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center gap-6 px-6 py-4">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-body-strong text-foreground">{title}</span>
        <span className="text-body-sm text-muted-foreground">{description}</span>
        {error ? <span className="text-caption text-destructive-text">{error}</span> : null}
      </div>
      <div className="flex shrink-0 items-center gap-2">{children}</div>
    </div>
  );
}

/** 멘토링 방식: 아이콘 선택 카드 두 개 (하나 이상) */
function ModeRow({ control, error }: { control: Control<SettingsForm>; error?: string }) {
  return (
    <div className="flex flex-col gap-3 px-6 py-4">
      <div className="flex flex-col gap-0.5">
        <span className="text-body-strong text-foreground">멘토링 방식</span>
        <span className="text-body-sm text-muted-foreground">신청받을 멘토링 종류를 하나 이상 골라요.</span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <ModeCard
          control={control}
          name="allow1on1"
          icon={UserRound}
          label="1:1 멘토링"
          description="수강생 한 명이 멘토에게 신청해요"
        />
        <ModeCard
          control={control}
          name="allowTeam"
          icon={Users}
          label="팀 멘토링"
          description="팀이 함께 신청해요 · 팀 관리 사용"
        />
      </div>
      {error ? <span className="text-caption text-destructive-text">{error}</span> : null}
    </div>
  );
}

function ModeCard({
  control,
  name,
  icon: Icon,
  label,
  description,
}: {
  control: Control<SettingsForm>;
  name: "allow1on1" | "allowTeam";
  icon: LucideIcon;
  label: string;
  description: string;
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <button
          type="button"
          role="switch"
          aria-checked={field.value}
          aria-label={label}
          onClick={() => field.onChange(!field.value)}
          className={cn(
            "group relative flex items-start gap-3 rounded-xl border p-4 text-left outline-none transition-all focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60",
            field.value
              ? "border-primary/50 bg-sidebar-accent shadow-sm"
              : "border-border bg-card hover:border-primary/30 hover:bg-muted/40",
          )}
        >
          <span
            className={cn(
              "inline-flex size-10 shrink-0 items-center justify-center rounded-lg transition-colors",
              field.value ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
            )}
          >
            <Icon aria-hidden className="size-5" />
          </span>
          <span className="flex min-w-0 flex-col gap-0.5 pr-6">
            <span
              className={cn("text-body-strong", field.value ? "text-sidebar-accent-foreground" : "text-foreground")}
            >
              {label}
            </span>
            <span className="text-caption text-muted-foreground">{description}</span>
          </span>
          <span
            aria-hidden
            className={cn(
              "absolute top-3 right-3 inline-flex size-5 items-center justify-center rounded-full border transition-colors",
              field.value ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card",
            )}
          >
            {field.value ? <Check className="size-3.5" strokeWidth={3} /> : null}
          </span>
        </button>
      )}
    />
  );
}

function Rules({ form }: { form: UseFormReturn<SettingsForm> }) {
  const errors = form.formState.errors;
  const segment = <N extends "duration" | "pending" | "lead">(
    name: N,
    label: string,
    options: readonly { value: SettingsForm[N]; label: string }[],
    width: string,
  ) => (
    <Controller
      control={form.control}
      name={name}
      render={({ field }) => (
        <Segmented label={label} value={field.value} onChange={field.onChange} options={options} className={width} />
      )}
    />
  );
  return (
    <>
      <SettingRow title="진행 단위" description="수강생이 고르는 신청 길이의 단위예요.">
        {segment(
          "duration",
          "진행 단위",
          [
            { value: "30", label: "30분" },
            { value: "60", label: "60분" },
          ],
          "w-44",
        )}
      </SettingRow>
      <SettingRow
        title="기본 지급 시간"
        description="일괄 지급에서 시간을 비우면 이만큼 줘요."
        error={errors.grant1on1?.message ?? errors.grantTeam?.message}
      >
        <HoursInput form={form} name="grant1on1" label="기본 지급 · 1:1" prefix="1:1" />
        <HoursInput form={form} name="grantTeam" label="기본 지급 · 팀" prefix="팀" />
      </SettingRow>
      <SettingRow title="대기 신청 수" description="한 번에 기다릴 수 있는 신청 수 (1:1은 수강생, 팀은 팀마다)">
        {segment(
          "pending",
          "대기 신청 수",
          [
            { value: "1", label: "1건" },
            { value: "2", label: "2건" },
            { value: "3", label: "3건" },
          ],
          "w-52",
        )}
      </SettingRow>
      <SettingRow title="신청·취소 마감" description="세션 시작 몇 시간 전까지 신청·취소할 수 있어요.">
        {segment(
          "lead",
          "신청·취소 마감",
          [
            { value: "6", label: "6시간 전" },
            { value: "12", label: "12시간 전" },
            { value: "24", label: "24시간 전" },
          ],
          "w-80",
        )}
      </SettingRow>
    </>
  );
}

/** 입력 묶음: 앞에 '1:1'·'팀', 뒤에 '시간' */
function HoursInput({
  form,
  name,
  label,
  prefix,
}: {
  form: UseFormReturn<SettingsForm>;
  name: "grant1on1" | "grantTeam";
  label: string;
  prefix: string;
}) {
  return (
    <label className="flex h-9 items-center overflow-hidden rounded-md border border-input bg-background focus-within:ring-2 focus-within:ring-ring">
      <span className="flex h-full items-center border-r border-input bg-muted px-2.5 text-caption-strong text-muted-foreground">
        {prefix}
      </span>
      <Input
        aria-label={label}
        inputMode="numeric"
        className="h-full w-14 rounded-none border-0 text-right shadow-none focus-visible:ring-0"
        {...form.register(name)}
      />
      <span className="pr-2.5 text-body-sm text-muted-foreground">시간</span>
    </label>
  );
}

function TimeSelect({
  control,
  name,
  label,
  options,
}: {
  control: Control<SettingsForm>;
  name: "weekdayStart" | "weekdayEnd" | "weekendStart" | "weekendEnd";
  label: string;
  options: string[];
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <Select value={field.value} onValueChange={field.onChange}>
          <SelectTrigger aria-label={label} className="w-24">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {options.map((t) => (
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

function minutesOf(t: string): number {
  const [h = 0, m = 0] = t.split(":").map(Number);
  return h * 60 + m;
}

/** 0~24시 막대에 운영 구간을 칠한다 */
function HoursTrack({ on, start, end }: { on: boolean; start: string; end: string }) {
  const s = (minutesOf(start) / 1440) * 100;
  const e = (minutesOf(end) / 1440) * 100;
  return (
    <div aria-hidden className="flex flex-col gap-1">
      <div className="relative h-2.5 overflow-hidden rounded-full bg-muted">
        {on && e > s ? (
          <div
            className="absolute inset-y-0 rounded-full bg-primary/70"
            // 운영 구간 위치는 값으로 계산 (인라인 스타일)
            style={{ left: `${s}%`, width: `${e - s}%` }}
          />
        ) : null}
        {[25, 50, 75].map((p) => (
          <span key={p} className="absolute inset-y-0 w-px bg-background/70" style={{ left: `${p}%` }} />
        ))}
      </div>
      <div className="flex justify-between text-caption text-muted-foreground">
        <span>0시</span>
        <span>6시</span>
        <span>12시</span>
        <span>18시</span>
        <span>24시</span>
      </div>
    </div>
  );
}

function HoursRow({
  form,
  icon: Icon,
  label,
  sub,
  help,
  on,
  start,
  end,
}: {
  form: UseFormReturn<SettingsForm>;
  icon: LucideIcon;
  label: string;
  sub: string;
  help?: string;
  on: "weekdayOn" | "weekendOn";
  start: "weekdayStart" | "weekendStart";
  end: "weekdayEnd" | "weekendEnd";
}) {
  const [enabled, from, to] = useWatch({ control: form.control, name: [on, start, end] });
  const error = form.formState.errors[end]?.message;
  return (
    <div className="flex flex-col gap-3 px-6 py-4">
      <div className="flex items-center gap-3">
        <span className="inline-flex size-8 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          <Icon aria-hidden className="size-4" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="flex items-center gap-1.5 text-body-strong text-foreground">
            {label}
            {help ? <HelpTip label={label}>{help}</HelpTip> : null}
            {help ? (
              <Link
                to="/admin/settings/holidays"
                className="text-caption font-normal text-primary-text hover:underline"
              >
                공휴일 보기
              </Link>
            ) : null}
          </span>
          <span className="text-caption text-muted-foreground">{sub}</span>
        </div>
        {enabled ? (
          <div className="flex items-center gap-2">
            <TimeSelect control={form.control} name={start} label={`${label} 시작`} options={START_TIMES} />
            <span aria-hidden className="text-muted-foreground">
              –
            </span>
            <TimeSelect control={form.control} name={end} label={`${label} 끝`} options={END_TIMES} />
          </div>
        ) : (
          <span className="text-body-sm text-muted-foreground">운영 안 함</span>
        )}
        <Controller
          control={form.control}
          name={on}
          render={({ field }) => (
            <Switch checked={field.value} onCheckedChange={field.onChange} aria-label={`${label} 운영`} />
          )}
        />
      </div>
      <HoursTrack on={enabled} start={from} end={to} />
      {error ? <span className="text-caption text-destructive-text">{error}</span> : null}
    </div>
  );
}

/** 오른쪽 위 한눈에 보기: 지금 입력값으로 바로 바뀐다 */
function Summary({ values: v }: { values: SettingsForm }) {
  const modes = [v.allow1on1 ? "1:1" : null, v.allowTeam ? "팀" : null].filter(Boolean).join(" · ") || "없음";
  const hours = (on: boolean, s: string, e: string) => (on ? `${s} – ${e}` : "운영 안 함");
  const rows: [LucideIcon, string, string][] = [
    [Users, "신청 받는 멘토링", modes],
    [Timer, "신청 길이", `${v.duration}분 단위`],
    [Wallet, "기본 지급", `1:1 ${v.grant1on1 || 0}시간 · 팀 ${v.grantTeam || 0}시간`],
    [Hourglass, "대기 신청", `최대 ${v.pending}건`],
    [CalendarClock, "신청·취소 마감", `시작 ${v.lead}시간 전`],
    [Sun, "평일", hours(v.weekdayOn, v.weekdayStart, v.weekdayEnd)],
    [Moon, "주말·공휴일", hours(v.weekendOn, v.weekendStart, v.weekendEnd)],
  ];
  return (
    <section
      aria-label="한눈에 보기"
      className="overflow-hidden rounded-2xl border border-primary/20 bg-linear-to-br from-sidebar-accent to-card shadow-sm"
    >
      <div className="flex items-center gap-2 px-5 pt-4 pb-3">
        <Sparkles aria-hidden className="size-4 text-primary-text" />
        <h2 className="text-body-strong text-foreground">한눈에 보기</h2>
      </div>
      <dl className="flex flex-col gap-2.5 px-5 pb-5">
        {rows.map(([Icon, label, value]) => (
          <div key={label} className="flex items-center gap-2.5">
            <Icon aria-hidden className="size-4 shrink-0 text-muted-foreground" />
            <dt className="flex-1 text-body-sm text-muted-foreground">{label}</dt>
            <dd className="text-body-strong text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function md(key: string): string {
  return `${Number(key.slice(5, 7))}.${Number(key.slice(8, 10))}`;
}

/** 금지 시간대 목록 (F86 점선 추가 카드, 항목·추가는 패널) */
function BlockTimes({ cohortId, title, canManage }: { cohortId: string; title: string; canManage: boolean }) {
  const blocks = useQuery(blockTimesQuery(cohortId));
  const [sheet, setSheet] = useState<BlockSheetState | null>(null);
  const items: BlockTime[] = [...(blocks.data ?? [])].sort(
    (a, b) => a.period_start.localeCompare(b.period_start) || a.start_time.localeCompare(b.start_time),
  );
  return (
    <section aria-label="금지 시간대" className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
      <div className="flex items-center gap-2 px-5 pt-4 pb-3">
        <CalendarOff aria-hidden className="size-4 text-muted-foreground" />
        <h2 className="flex flex-1 items-center gap-1.5 text-body-strong text-foreground">
          금지 시간대
          <HelpTip label="금지 시간대">{HELP.blocks}</HelpTip>
        </h2>
        <span className="rounded-full bg-muted px-2 py-0.5 text-caption text-muted-foreground">평일만</span>
      </div>
      <div className="flex flex-col gap-2 px-5 pb-5">
        {canManage ? (
          <button
            type="button"
            onClick={() => setSheet({ mode: "add" })}
            className="flex items-center justify-center gap-2 rounded-xl border border-dashed border-primary/40 bg-sidebar-accent/40 px-4 py-3 text-body-strong text-sidebar-accent-foreground outline-none transition-colors hover:border-primary/70 hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Plus aria-hidden className="size-4" />
            금지 시간대 추가
          </button>
        ) : null}
        {blocks.isPending ? (
          <Spinner />
        ) : blocks.isError ? (
          <ErrorState onRetry={() => void blocks.refetch()} />
        ) : items.length === 0 ? (
          <p className="py-4 text-center text-body-sm text-muted-foreground">등록한 금지 시간대가 없어요.</p>
        ) : (
          <ul aria-label="금지 시간대 목록" className="flex flex-col gap-2">
            {items.map((b) => (
              <li key={b.id}>
                <button
                  type="button"
                  aria-label={`${md(b.period_start)} ~ ${md(b.period_end)} · ${b.start_time.slice(0, 5)} ~ ${b.end_time.slice(0, 5)}`}
                  onClick={() => setSheet({ mode: "view", block: b })}
                  className="group flex w-full items-center gap-3 rounded-xl border border-border bg-card p-3 text-left outline-none transition-all hover:border-primary/30 hover:shadow-sm focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="flex w-16 shrink-0 flex-col items-center rounded-lg bg-muted py-1.5 text-center">
                    <span className="text-caption-strong text-foreground">{md(b.period_start)}</span>
                    <span className="text-caption text-muted-foreground">~ {md(b.period_end)}</span>
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="inline-flex w-fit items-center gap-1 rounded-md bg-sidebar-accent px-2 py-0.5 text-caption-strong text-sidebar-accent-foreground">
                      <Clock aria-hidden className="size-3" />
                      {b.start_time.slice(0, 5)} – {b.end_time.slice(0, 5)}
                    </span>
                    <span className="truncate text-body-sm text-muted-foreground">{b.reason ?? "사유 없음"}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <BlockTimeSheet cohortId={cohortId} cohortTitle={title} state={sheet} canManage={canManage} onChange={setSheet} />
    </section>
  );
}

/** 아래 고정 저장 막대: 상태 + [되돌리기][저장] */
function SaveBar({
  dirty,
  canSave,
  pending,
  onReset,
}: {
  dirty: boolean;
  canSave: boolean;
  pending: boolean;
  onReset: () => void;
}) {
  return (
    <div className="sticky bottom-4 z-10">
      <div
        className={cn(
          "flex items-center gap-3 rounded-2xl border px-5 py-3 shadow-lg backdrop-blur transition-colors",
          dirty ? "border-primary/40 bg-card/95" : "border-info/40 bg-card/95",
        )}
      >
        <span aria-hidden className={cn("size-2 rounded-full", dirty ? "bg-warning" : "bg-info")} />
        <span className="flex-1 text-body text-foreground">
          {dirty ? "저장하지 않은 변경이 있어요" : "기본값으로 저장하면 이 기수에서 신청을 받을 수 있어요"}
        </span>
        {dirty ? (
          <Button type="button" variant="ghost" onClick={onReset} disabled={pending}>
            되돌리기
          </Button>
        ) : null}
        <Button type="submit" form={FORM_ID} disabled={!canSave}>
          저장
        </Button>
      </div>
    </div>
  );
}
