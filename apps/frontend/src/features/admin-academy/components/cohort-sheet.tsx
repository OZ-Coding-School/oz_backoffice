import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useId, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ErrorState } from "@/components/error-state";
import { PanelActions, PanelHead, PanelList, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { ENROLLMENT_LABELS } from "@/features/admin-members/api";
import { DiscardDialog } from "@/features/admin-org/components/shared";
import { errorText } from "@/features/admin-org/text";
import { hasPermission, type StaffAccess } from "@/features/staff/api";

import {
  cohortQuery,
  cohortSettingsQuery,
  cohortSummaryQuery,
  useSaveCohort,
  type Bootcamp,
  type Cohort,
  type CohortStatus,
} from "../api";
import { COHORT_STATUS, COHORT_STATUS_ORDER, hoursLabel, hrdLabel, periodLabel } from "../labels";

const SYNC_HELP = "과정·기수·기간·HRD 회차는 Airtable 명단 동기화가 정해요. 여기서는 바꿀 수 없어요.";
const STATUS_HELP =
  "개강 전·진행 중·종료는 동기화가 Airtable 진행상태로 바꿔요. 비활성·보관은 운영진이 정하고, 동기화가 덮어쓰지 않아요. 보관한 기수는 목록에서 숨겨요.";
const ENROLLMENT_ORDER = ["ENROLLED", "COMPLETED", "DROPPED", "EARLY_EMPLOYED", "TRANSFERRED"];

const schema = z.object({
  status: z.enum(["PLANNED", "ONGOING", "ENDED", "INACTIVE", "ARCHIVED"]),
  discord_guild_id: z.string().trim().max(32, "디스코드 서버 ID는 32자까지예요.").regex(/^\d*$/, "숫자만 적어 주세요."),
});
type Values = z.infer<typeof schema>;

/** 기수 패널 (F68·F74): 기본 정보(조회만)·운영(수정)·수강생·멘토·담당자·멘토링 설정 */
export function CohortSheet({
  cohortId,
  bootcamp,
  access,
  onClose,
}: {
  cohortId: string;
  bootcamp: Bootcamp;
  access: StaffAccess;
  onClose: () => void;
}) {
  const cohort = useQuery(cohortQuery(cohortId));
  const canManage = hasPermission(access, "academy.cohort.manage");
  const [editing, setEditing] = useState(false);
  const c = cohort.data;
  const status = c ? COHORT_STATUS[c.status] : null;
  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined}>
        <PanelHead
          title={c ? `${c.cohort_number}기` : "기수"}
          description={`${bootcamp.name} · 기수`}
          badges={
            editing ? (
              <Badge variant="info">수정 중</Badge>
            ) : status ? (
              <Badge variant={status.variant}>{status.label}</Badge>
            ) : null
          }
          actions={c && canManage && !editing ? <PanelActions onEdit={() => setEditing(true)} /> : null}
          onClose={onClose}
        />
        {cohort.isPending ? (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        ) : cohort.isError || !c ? (
          <ErrorState className="m-6" onRetry={() => void cohort.refetch()} />
        ) : editing ? (
          <CohortForm cohort={c} bootcamp={bootcamp} onDone={() => setEditing(false)} />
        ) : (
          <CohortView cohort={c} bootcamp={bootcamp} access={access} />
        )}
      </SheetContent>
    </Sheet>
  );
}

function BasicSection({ cohort: c, bootcamp }: { cohort: Cohort; bootcamp: Bootcamp }) {
  return (
    <PanelSection title="기본 정보">
      <PanelRow label="과정">{bootcamp.name}</PanelRow>
      <PanelRow label="기수">{c.cohort_number}기</PanelRow>
      <PanelRow label="기간">{periodLabel(c.start_date, c.end_date)}</PanelRow>
      <PanelRow label="HRD 회차">{hrdLabel(c.hrd_net_id, c.hrd_cohort_number)}</PanelRow>
      <PanelRow label="동기화" help={SYNC_HELP}>
        Airtable
      </PanelRow>
    </PanelSection>
  );
}

function CohortView({ cohort: c, bootcamp, access }: { cohort: Cohort; bootcamp: Bootcamp; access: StaffAccess }) {
  const summary = useQuery(cohortSummaryQuery(c.id));
  const canSeeSettings = hasPermission(access, "mentoring.settings.read");
  const settings = useQuery({ ...cohortSettingsQuery(c.id), enabled: canSeeSettings });
  const s = summary.data;
  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
      <BasicSection cohort={c} bootcamp={bootcamp} />
      <PanelSection title="운영">
        <PanelRow label="상태" help={STATUS_HELP}>
          {COHORT_STATUS[c.status].label}
        </PanelRow>
        <PanelRow label="디스코드 서버">
          <span className="break-all">{c.discord_guild_id ?? "—"}</span>
        </PanelRow>
      </PanelSection>
      {summary.isError ? <Alert variant="error" title="운영 정보를 불러오지 못했어요." /> : null}
      {s ? (
        <>
          <PanelSection title={`수강생 ${s.students.total}명`}>
            <PanelRow label="가입">{s.students.linked}명</PanelRow>
            {ENROLLMENT_ORDER.map((status) => (
              <PanelRow key={status} label={ENROLLMENT_LABELS[status] ?? status}>
                {s.students.by_status[status] ?? 0}명
              </PanelRow>
            ))}
          </PanelSection>
          <PanelSection title={`멘토 ${s.mentors.length}명`}>
            {s.mentors.length ? (
              <PanelList
                label="멘토"
                items={s.mentors.map((m) => ({
                  id: m.mentor_id,
                  name: m.name,
                  meta: `${Number(m.start_date.slice(5, 7))}/${Number(m.start_date.slice(8))}부터`,
                }))}
              />
            ) : (
              <p className="text-body text-muted-foreground">배정된 멘토가 없어요.</p>
            )}
          </PanelSection>
          <PanelSection title={`담당자 ${s.staff.length}명`}>
            {s.staff.length ? (
              <PanelList
                label="담당자"
                items={s.staff.map((x) => ({
                  id: x.employee_id,
                  name: x.name,
                  meta: [x.position_name, x.scope === "COHORT" ? "기수" : "과정"].filter(Boolean).join(" · "),
                }))}
              />
            ) : (
              <p className="text-body text-muted-foreground">담당자가 없어요.</p>
            )}
          </PanelSection>
        </>
      ) : summary.isPending ? (
        <p className="text-body text-muted-foreground">운영 정보를 불러오는 중…</p>
      ) : null}
      {canSeeSettings ? (
        <PanelSection title="멘토링 설정">
          {settings.data === null ? (
            <p className="text-body text-muted-foreground">설정 전이에요.</p>
          ) : settings.data ? (
            <>
              <PanelRow label="신청 유형">
                {[settings.data.allow_1_on_1 ? "1:1" : null, settings.data.allow_team_mentoring ? "팀" : null]
                  .filter(Boolean)
                  .join(" · ") || "—"}
              </PanelRow>
              <PanelRow label="진행 단위">{settings.data.allowed_duration}분</PanelRow>
              <PanelRow label="신청 마감">{settings.data.min_lead_hours}시간 전</PanelRow>
              <PanelRow label="평일">{hoursLabel(settings.data.weekday_hours)}</PanelRow>
              <PanelRow label="주말·공휴일">{hoursLabel(settings.data.weekend_hours)}</PanelRow>
            </>
          ) : settings.isError ? (
            <p className="text-body text-muted-foreground">멘토링 설정을 볼 수 없어요.</p>
          ) : (
            <p className="text-body text-muted-foreground">불러오는 중…</p>
          )}
        </PanelSection>
      ) : null}
    </div>
  );
}

function CohortForm({ cohort: c, bootcamp, onDone }: { cohort: Cohort; bootcamp: Bootcamp; onDone: () => void }) {
  const id = useId();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { status: c.status, discord_guild_id: c.discord_guild_id ?? "" },
  });
  const save = useSaveCohort(c);
  const [error, setError] = useState<string | null>(null);
  const dirty = form.formState.isDirty;
  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !save.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });
  const { errors } = form.formState;
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    const body: { status?: CohortStatus; discord_guild_id?: string | null } = {};
    if (v.status !== c.status) body.status = v.status;
    const discord = v.discord_guild_id.trim() || null;
    if (discord !== (c.discord_guild_id ?? null)) body.discord_guild_id = discord;
    try {
      if (Object.keys(body).length) await save.mutateAsync(body);
      form.reset(v);
      toast.success(`${bootcamp.name} ${c.cohort_number}기를 저장했어요`);
      onDone();
    } catch (e) {
      setError(errorText(e));
    }
  });
  return (
    <form aria-label="기수 수정" noValidate onSubmit={(e) => void onSubmit(e)} className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
        <BasicSection cohort={c} bootcamp={bootcamp} />
        <PanelSection title="운영">
          <PanelRow label="상태" htmlFor={`${id}-status`} help={STATUS_HELP}>
            <Controller
              control={form.control}
              name="status"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id={`${id}-status`} className="font-normal">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {COHORT_STATUS_ORDER.map((s) => (
                      <SelectItem key={s} value={s}>
                        {COHORT_STATUS[s].label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </PanelRow>
          <PanelRow label="디스코드 서버" htmlFor={`${id}-discord`}>
            <Input
              id={`${id}-discord`}
              inputMode="numeric"
              maxLength={32}
              placeholder="서버 ID (숫자)"
              aria-invalid={!!errors.discord_guild_id}
              className="font-normal"
              {...form.register("discord_guild_id")}
            />
            {errors.discord_guild_id ? (
              <p className="mt-1 text-caption font-normal text-destructive-text">{errors.discord_guild_id.message}</p>
            ) : null}
          </PanelRow>
        </PanelSection>
        {error ? <Alert variant="error" title={error} /> : null}
      </div>
      <div className="flex justify-end gap-2 border-t border-border px-6 py-3">
        <Button type="button" variant="outline" onClick={onDone}>
          취소
        </Button>
        <Button type="submit" disabled={save.isPending}>
          저장
        </Button>
      </div>
      <DiscardDialog blocker={blocker} />
    </form>
  );
}
