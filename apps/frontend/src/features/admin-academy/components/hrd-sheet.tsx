import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Link, useBlocker } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";
import { useId, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { PanelActions, PanelHead, PanelList, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { DiscardDialog } from "@/features/admin-org/components/shared";
import { errorText } from "@/features/admin-org/text";
import { hasPermission, type StaffAccess } from "@/features/staff/api";

import { hrdCohortsQuery, useSaveHrdBootcamp, type HrdBootcamp, type HrdBootcampChanges } from "../api";
import { amount, DAY_NIGHT_LABELS, optionalPeriod, TRAIN_TYPE_LABELS, WEEKEND_LABELS, won } from "../labels";

const NONE = "none";
const SYNC_HELP = "훈련과정 ID와 회차 번호·기간은 Airtable 명단 동기화가 정해요. 여기서는 바꿀 수 없어요.";
const NCS_HELP = "NCS 대·중·소분류 코드예요.";

const count = z.string().trim().regex(/^\d*$/, "0 이상의 숫자만 적어 주세요.").max(10, "숫자가 너무 커요.");
const code = z.string().trim().max(10, "10자까지예요.");
const schema = z.object({
  name: z.string().trim().min(1, "이름을 적어 주세요.").max(100, "100자까지예요."),
  train_type: z.enum(["KDT", "KDC", NONE]),
  ncs1_se: code,
  ncs2_se: code,
  ncs3_se: code,
  weekend_se: z.enum(["WEEKDAY", "WEEKEND", "HYBRID"]),
  day_night_se: z.enum(["DAY", "NIGHT", "HYBRID"]),
  total_train_fee: count,
  train_fee_per_hour: count,
  total_train_hours: count,
  total_train_days: count,
});
type Values = z.infer<typeof schema>;

const toNumber = (v: string) => (v.trim() ? Number(v.trim()) : null);
const toText = (v: string) => v.trim() || null;

function ncsLabel(h: HrdBootcamp): string {
  return [h.ncs1_se, h.ncs2_se, h.ncs3_se].filter(Boolean).join(" › ") || "—";
}

/** HRD 과정 패널 (F68·F75): 기본 정보·훈련 정보·연결 운영과정·회차 */
export function HrdSheet({ hrd: h, access, onClose }: { hrd: HrdBootcamp; access: StaffAccess; onClose: () => void }) {
  const canManage = hasPermission(access, "academy.hrd.manage");
  const [editing, setEditing] = useState(false);
  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined}>
        <PanelHead
          title={h.name}
          description={`HRD 과정${h.hrd_net_id ? ` · ${h.hrd_net_id}` : ""}`}
          badges={
            editing ? (
              <Badge variant="info">수정 중</Badge>
            ) : h.train_type ? (
              <Badge>{TRAIN_TYPE_LABELS[h.train_type] ?? h.train_type}</Badge>
            ) : null
          }
          actions={canManage && !editing ? <PanelActions onEdit={() => setEditing(true)} /> : null}
          onClose={onClose}
        />
        {editing ? <HrdForm hrd={h} onDone={() => setEditing(false)} /> : <HrdView hrd={h} />}
      </SheetContent>
    </Sheet>
  );
}

function HrdView({ hrd: h }: { hrd: HrdBootcamp }) {
  const cohorts = useQuery(hrdCohortsQuery(h.id));
  const ordered = [...(cohorts.data ?? [])].sort((a, b) => b.cohort_number - a.cohort_number);
  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
      <PanelSection title="기본 정보">
        <PanelRow label="이름">{h.name}</PanelRow>
        <PanelRow label="훈련과정 ID">{h.hrd_net_id ?? "—"}</PanelRow>
        <PanelRow label="동기화" help={SYNC_HELP}>
          Airtable
        </PanelRow>
      </PanelSection>
      <PanelSection title="훈련 정보">
        <PanelRow label="훈련 유형">{h.train_type ? (TRAIN_TYPE_LABELS[h.train_type] ?? h.train_type) : "—"}</PanelRow>
        <PanelRow label="NCS" help={NCS_HELP}>
          {ncsLabel(h)}
        </PanelRow>
        <PanelRow label="주말·야간">
          {WEEKEND_LABELS[h.weekend_se] ?? h.weekend_se} · {DAY_NIGHT_LABELS[h.day_night_se] ?? h.day_night_se}
        </PanelRow>
        <PanelRow label="총 훈련비">{won(h.total_train_fee)}</PanelRow>
        <PanelRow label="시간당 훈련비">{won(h.train_fee_per_hour)}</PanelRow>
        <PanelRow label="총 훈련 시간">{amount(h.total_train_hours, "시간")}</PanelRow>
        <PanelRow label="총 훈련 일수">{amount(h.total_train_days, "일")}</PanelRow>
      </PanelSection>
      <PanelSection title={`연결 운영과정 ${(h.bootcamps ?? []).length}개`}>
        {(h.bootcamps ?? []).length ? (
          <PanelList
            label="연결 운영과정"
            items={(h.bootcamps ?? []).map((b) => ({ id: b.id, name: b.name, meta: b.code }))}
          />
        ) : (
          <p className="text-body text-muted-foreground">연결된 운영과정이 없어요.</p>
        )}
      </PanelSection>
      <PanelSection title={`회차 ${h.cohort_count}개`}>
        {cohorts.isError ? (
          <Alert variant="error" title="회차를 불러오지 못했어요." />
        ) : cohorts.isPending ? (
          <p className="text-body text-muted-foreground">불러오는 중…</p>
        ) : ordered.length ? (
          <ul aria-label="회차" className="divide-y divide-border overflow-hidden rounded-md border border-border">
            {ordered.map((c) => (
              <li key={c.id}>
                <Link
                  to="/admin/academy/hrd"
                  search={{ hrd: h.id, cohort: c.id }}
                  className="flex min-h-10 items-center gap-2 py-2 pr-2 pl-3 outline-none hover:bg-accent/60 focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="w-14 shrink-0 text-body-strong text-foreground">{c.cohort_number}회차</span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="text-caption text-muted-foreground">
                      {optionalPeriod(c.train_start_date, c.train_end_date)}
                    </span>
                    <span className="truncate text-body text-foreground">
                      {(c.linked_cohorts ?? []).map((l) => `${l.bootcamp_name} ${l.cohort_number}기`).join(", ") ||
                        "연결된 기수 없음"}
                    </span>
                  </span>
                  <ChevronRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-body text-muted-foreground">회차가 없어요.</p>
        )}
      </PanelSection>
    </div>
  );
}

function HrdForm({ hrd: h, onDone }: { hrd: HrdBootcamp; onDone: () => void }) {
  const id = useId();
  const text = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v));
  const defaults: Values = {
    name: h.name,
    train_type: h.train_type ?? NONE,
    ncs1_se: h.ncs1_se ?? "",
    ncs2_se: h.ncs2_se ?? "",
    ncs3_se: h.ncs3_se ?? "",
    weekend_se: h.weekend_se,
    day_night_se: h.day_night_se,
    total_train_fee: text(h.total_train_fee),
    train_fee_per_hour: text(h.train_fee_per_hour),
    total_train_hours: text(h.total_train_hours),
    total_train_days: text(h.total_train_days),
  };
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: defaults });
  const save = useSaveHrdBootcamp(h.id);
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
    const body: HrdBootcampChanges = {
      name: v.name.trim(),
      train_type: v.train_type === NONE ? null : v.train_type,
      ncs1_se: toText(v.ncs1_se),
      ncs2_se: toText(v.ncs2_se),
      ncs3_se: toText(v.ncs3_se),
      weekend_se: v.weekend_se,
      day_night_se: v.day_night_se,
      total_train_fee: toNumber(v.total_train_fee),
      train_fee_per_hour: toNumber(v.train_fee_per_hour),
      total_train_hours: toNumber(v.total_train_hours),
      total_train_days: toNumber(v.total_train_days),
    };
    try {
      await save.mutateAsync(body);
      form.reset(v);
      toast.success(`${v.name.trim()} HRD 과정을 저장했어요`);
      onDone();
    } catch (e) {
      setError(errorText(e));
    }
  });
  const numberField = (name: keyof Values, label: string, unit: string) => (
    <PanelRow label={label} htmlFor={`${id}-${name}`}>
      <span className="flex items-center gap-2 font-normal">
        <Input
          id={`${id}-${name}`}
          inputMode="numeric"
          aria-invalid={!!errors[name]}
          className="font-normal"
          {...form.register(name)}
        />
        <span className="w-8 shrink-0 text-body text-muted-foreground">{unit}</span>
      </span>
      {errors[name] ? (
        <p className="mt-1 text-caption font-normal text-destructive-text">{errors[name]?.message}</p>
      ) : null}
    </PanelRow>
  );
  return (
    <form
      aria-label="HRD 과정 수정"
      noValidate
      onSubmit={(e) => void onSubmit(e)}
      className="flex min-h-0 flex-1 flex-col"
    >
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
        <PanelSection title="기본 정보">
          <PanelRow label="이름" htmlFor={`${id}-name`}>
            <Input
              id={`${id}-name`}
              maxLength={100}
              aria-invalid={!!errors.name}
              className="font-normal"
              {...form.register("name")}
            />
            {errors.name ? (
              <p className="mt-1 text-caption font-normal text-destructive-text">{errors.name.message}</p>
            ) : null}
          </PanelRow>
          <PanelRow label="훈련과정 ID">{h.hrd_net_id ?? "—"}</PanelRow>
          <PanelRow label="동기화" help={SYNC_HELP}>
            Airtable
          </PanelRow>
        </PanelSection>
        <PanelSection title="훈련 정보">
          <PanelRow label="훈련 유형" htmlFor={`${id}-type`}>
            <Controller
              control={form.control}
              name="train_type"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id={`${id}-type`} className="font-normal">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="KDT">KDT</SelectItem>
                    <SelectItem value="KDC">KDC</SelectItem>
                    <SelectItem value={NONE}>없음</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </PanelRow>
          <PanelRow label="NCS" htmlFor={`${id}-ncs1`} help={NCS_HELP}>
            <span className="grid grid-cols-3 gap-2">
              {(["ncs1_se", "ncs2_se", "ncs3_se"] as const).map((n, i) => (
                <Input
                  key={n}
                  id={i === 0 ? `${id}-ncs1` : undefined}
                  aria-label={["NCS 대분류", "NCS 중분류", "NCS 소분류"][i]}
                  maxLength={10}
                  className="font-normal"
                  {...form.register(n)}
                />
              ))}
            </span>
          </PanelRow>
          <PanelRow label="주말·야간" htmlFor={`${id}-weekend`}>
            <span className="grid grid-cols-2 gap-2">
              <Controller
                control={form.control}
                name="weekend_se"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id={`${id}-weekend`} aria-label="주말 구분" className="font-normal">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(WEEKEND_LABELS).map(([k, v]) => (
                        <SelectItem key={k} value={k}>
                          {v}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              <Controller
                control={form.control}
                name="day_night_se"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger aria-label="주야간 구분" className="font-normal">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(DAY_NIGHT_LABELS).map(([k, v]) => (
                        <SelectItem key={k} value={k}>
                          {v}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </span>
          </PanelRow>
          {numberField("total_train_fee", "총 훈련비", "원")}
          {numberField("train_fee_per_hour", "시간당 훈련비", "원")}
          {numberField("total_train_hours", "총 훈련 시간", "시간")}
          {numberField("total_train_days", "총 훈련 일수", "일")}
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
