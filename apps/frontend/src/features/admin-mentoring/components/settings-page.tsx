import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Link, useBlocker } from "@tanstack/react-router";
import { ChevronRight, Plus } from "lucide-react";
import { useId, useState, type ReactNode } from "react";
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

import { blockTimesQuery, useSaveSettings, type BlockTime, type MentoringSettings } from "../api";
import {
  blockLabel,
  END_TIMES,
  settingsBody,
  settingsForm,
  settingsSchema,
  START_TIMES,
  type SettingsForm,
} from "../form";
import { BlockTimeSheet, type BlockSheetState } from "./block-time-sheet";

const HELP = {
  mode: "수강생이 신청할 수 있는 멘토링 종류예요. 하나 이상 허용해야 해요. 팀 멘토링을 켜면 팀 관리를 써요.",
  duration: "수강생이 고르는 신청 길이의 단위예요.",
  grant1on1: "1:1 시간 계좌를 일괄 지급할 때 시간을 비우면 이 값을 줘요.",
  grantTeam: "팀 시간 계좌를 일괄 지급할 때 시간을 비우면 이 값을 줘요.",
  pending: "한 번에 기다릴 수 있는 신청 수예요. 1:1은 수강생마다, 팀은 팀마다 세요.",
  lead: "세션 시작 몇 시간 전까지 신청·취소할 수 있는지예요.",
  hours: "수강생은 이 시간 안에서만 신청해요. 멘토의 개인 일정·금지 시간대·세션은 빠져요.",
  weekend: "토·일과 공휴일에 적용돼요. 공휴일은 설정 > 공휴일에서 관리해요.",
  blocks:
    "수업 시간처럼 신청을 막을 시간이에요. 평일(월~금)에만 적용되고 주말·공휴일은 빼요. 등록 전 신청·세션에는 영향이 없어요.",
};

const FORM_ID = "mentoring-settings-form";

const ERROR_MESSAGES: Record<string, string> = {
  mentoring_mode_required: "1:1과 팀 멘토링 중 하나 이상을 허용해 주세요.",
  invalid_allowed_duration: "진행 단위는 30분 또는 60분이에요.",
  invalid_min_lead_hours: "신청 마감은 6·12·24시간 중에서 골라 주세요.",
  invalid_max_pending_requests: "대기 신청 수는 1~3건이에요.",
  invalid_default_minutes: "기본 지급 시간은 시간 단위로 적어 주세요.",
  invalid_operating_hours: "운영시간을 다시 확인해 주세요.",
};

/** 멘토링 설정 (Figma `멘토링 설정 (FE-19a)`, F90·A34·A37). 기본 규칙·운영시간은 [저장], 금지 시간대는 패널 */
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
  const sub = settings?.updated_at
    ? `${title} · 마지막 저장 ${formatKst(settings.updated_at, "MM/dd HH:mm")}`
    : `${title} · 아직 저장하지 않았어요`;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start gap-3">
        <div className="flex flex-1 flex-col gap-1">
          <h1 className="text-h1 text-foreground">멘토링 설정</h1>
          <p className="text-body text-muted-foreground">{sub}</p>
        </div>
        {canManage ? (
          <Button type="submit" form={FORM_ID} disabled={!canSave}>
            저장
          </Button>
        ) : null}
      </div>
      {!settings ? (
        <Alert
          title="아직 저장하지 않은 기수예요"
          description="기본값을 확인하고 저장하면 이 기수에서 멘토링 신청을 받을 수 있어요."
        />
      ) : null}
      {error ? <Alert variant="error" title={error} /> : null}
      <div className="grid grid-cols-[minmax(0,40rem)_minmax(0,1fr)] items-start gap-6">
        {/* 금지 시간대 패널의 폼이 이 폼으로 제출되지 않게 폼은 왼쪽 열만 감싼다 */}
        <form id={FORM_ID} aria-label="멘토링 설정" noValidate onSubmit={(e) => void onSubmit(e)}>
          <fieldset disabled={!canManage} className="flex min-w-0 flex-col gap-6">
            <Card title="기본 규칙">
              <Rules form={form} />
            </Card>
            <Card title="운영시간" help={HELP.hours}>
              <HoursRow form={form} label="평일 (월~금)" on="weekdayOn" start="weekdayStart" end="weekdayEnd" />
              <HoursRow
                form={form}
                label="주말·공휴일"
                help={HELP.weekend}
                on="weekendOn"
                start="weekendStart"
                end="weekendEnd"
                extra={
                  <Link
                    to="/admin/settings/holidays"
                    className="inline-flex items-center gap-0.5 text-caption text-muted-foreground hover:text-foreground"
                  >
                    공휴일 보기
                    <ChevronRight aria-hidden className="size-3" />
                  </Link>
                }
              />
            </Card>
          </fieldset>
        </form>
        <BlockTimes cohortId={cohortId} title={title} canManage={canManage} />
      </div>
      <DiscardDialog blocker={blocker} />
    </div>
  );
}

/** 섹션 상자 (F68과 같은 모양: 테두리 + 회색 머리) */
function Card({ title, help, children }: { title: string; help?: string; children: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex items-center gap-1.5 border-b border-border bg-muted px-4 py-3">
        <h2 id={id} className="text-body-strong text-foreground">
          {title}
        </h2>
        {help ? <HelpTip label={title}>{help}</HelpTip> : null}
      </div>
      <div className="flex flex-col gap-4 p-4">{children}</div>
    </section>
  );
}

/** '라벨 | 값' 한 줄 (라벨 128px) */
function Row({ label, help, error, children }: { label: string; help?: string; error?: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[8rem_minmax(0,1fr)] items-center gap-3">
      <span className="flex items-center gap-1 text-body text-muted-foreground">
        {label}
        {help ? <HelpTip label={label}>{help}</HelpTip> : null}
      </span>
      <div className="flex min-w-0 flex-col gap-1">
        {children}
        {error ? <p className="text-caption text-destructive-text">{error}</p> : null}
      </div>
    </div>
  );
}

function SwitchField({
  control,
  name,
  label,
}: {
  control: Control<SettingsForm>;
  name: "allow1on1" | "allowTeam";
  label: string;
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <label className="inline-flex items-center gap-2 text-body-strong text-foreground">
          <Switch checked={field.value} onCheckedChange={field.onChange} aria-label={label} />
          {label}
        </label>
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
      <Row label="멘토링 방식" help={HELP.mode} error={errors.allow1on1?.message}>
        <div className="flex flex-wrap gap-5">
          <SwitchField control={form.control} name="allow1on1" label="1:1 멘토링" />
          <SwitchField control={form.control} name="allowTeam" label="팀 멘토링" />
        </div>
      </Row>
      <Row label="진행 단위" help={HELP.duration}>
        {segment(
          "duration",
          "진행 단위",
          [
            { value: "30", label: "30분" },
            { value: "60", label: "60분" },
          ],
          "w-44",
        )}
      </Row>
      <Row label="기본 지급 · 1:1" help={HELP.grant1on1} error={errors.grant1on1?.message}>
        <HoursInput form={form} name="grant1on1" label="기본 지급 · 1:1" />
      </Row>
      <Row label="기본 지급 · 팀" help={HELP.grantTeam} error={errors.grantTeam?.message}>
        <HoursInput form={form} name="grantTeam" label="기본 지급 · 팀" />
      </Row>
      <Row label="대기 신청 수" help={HELP.pending}>
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
      </Row>
      <Row label="신청·취소 마감" help={HELP.lead}>
        {segment(
          "lead",
          "신청·취소 마감",
          [
            { value: "6", label: "시작 6시간 전" },
            { value: "12", label: "12시간 전" },
            { value: "24", label: "24시간 전" },
          ],
          "w-96",
        )}
      </Row>
    </>
  );
}

function HoursInput({
  form,
  name,
  label,
}: {
  form: UseFormReturn<SettingsForm>;
  name: "grant1on1" | "grantTeam";
  label: string;
}) {
  return (
    <span className="flex items-center gap-2">
      <Input aria-label={label} inputMode="numeric" className="w-24" {...form.register(name)} />
      <span className="text-body text-muted-foreground">시간</span>
    </span>
  );
}

function TimeSelect({
  control,
  name,
  label,
  options,
  disabled,
}: {
  control: Control<SettingsForm>;
  name: "weekdayStart" | "weekdayEnd" | "weekendStart" | "weekendEnd";
  label: string;
  options: string[];
  disabled: boolean;
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <Select value={field.value} onValueChange={field.onChange} disabled={disabled}>
          <SelectTrigger aria-label={label} className="w-28">
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

function HoursRow({
  form,
  label,
  help,
  on,
  start,
  end,
  extra,
}: {
  form: UseFormReturn<SettingsForm>;
  label: string;
  help?: string;
  on: "weekdayOn" | "weekendOn";
  start: "weekdayStart" | "weekendStart";
  end: "weekdayEnd" | "weekendEnd";
  extra?: ReactNode;
}) {
  const enabled = useWatch({ control: form.control, name: on });
  return (
    <Row label={label} help={help} error={form.formState.errors[end]?.message}>
      <div className="flex flex-wrap items-center gap-2.5">
        <Controller
          control={form.control}
          name={on}
          render={({ field }) => (
            <Switch checked={field.value} onCheckedChange={field.onChange} aria-label={`${label} 운영`} />
          )}
        />
        {enabled ? (
          <>
            <TimeSelect
              control={form.control}
              name={start}
              label={`${label} 시작`}
              options={START_TIMES}
              disabled={false}
            />
            <span aria-hidden className="text-muted-foreground">
              ~
            </span>
            <TimeSelect control={form.control} name={end} label={`${label} 끝`} options={END_TIMES} disabled={false} />
          </>
        ) : (
          <span className="text-body text-muted-foreground">운영 안 함</span>
        )}
        {extra}
      </div>
    </Row>
  );
}

/** 금지 시간대 목록 (F86 점선 추가 카드, 항목·추가는 패널) */
function BlockTimes({ cohortId, title, canManage }: { cohortId: string; title: string; canManage: boolean }) {
  const blocks = useQuery(blockTimesQuery(cohortId));
  const [sheet, setSheet] = useState<BlockSheetState | null>(null);
  const items: BlockTime[] = [...(blocks.data ?? [])].sort(
    (a, b) => a.period_start.localeCompare(b.period_start) || a.start_time.localeCompare(b.start_time),
  );
  return (
    <Card title="금지 시간대" help={HELP.blocks}>
      {canManage ? (
        <button
          type="button"
          onClick={() => setSheet({ mode: "add" })}
          className="flex items-center justify-center gap-2 rounded-lg border border-dashed border-primary/40 bg-sidebar-accent/40 px-4 py-3 text-body-strong text-sidebar-accent-foreground outline-none transition-colors hover:border-primary/70 hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-ring"
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
        <p className="text-body-sm text-muted-foreground">등록한 금지 시간대가 없어요.</p>
      ) : (
        <ul aria-label="금지 시간대 목록" className="flex flex-col gap-2">
          {items.map((b) => (
            <li key={b.id}>
              <button
                type="button"
                onClick={() => setSheet({ mode: "view", block: b })}
                className="flex w-full items-center gap-2 rounded-lg border border-border px-3.5 py-3 text-left outline-none hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-body-strong text-foreground">{blockLabel(b)}</span>
                  {b.reason ? <span className="truncate text-caption text-muted-foreground">{b.reason}</span> : null}
                </span>
                <ChevronRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <BlockTimeSheet cohortId={cohortId} cohortTitle={title} state={sheet} canManage={canManage} onChange={setSheet} />
    </Card>
  );
}
