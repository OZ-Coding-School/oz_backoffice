import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useId, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ErrorState } from "@/components/error-state";
import { PanelHead, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { DiscardDialog } from "@/features/admin-org/components/shared";
import { COHORT_STATUS } from "@/features/admin-academy/labels";
import { staffAccessQuery, type StaffCohort } from "@/features/staff/api";
import { formatKst } from "@/lib/datetime";

import { mentorAssignmentsQuery, type MentorAssignment, type MentorItem } from "../api";
import {
  assignmentError,
  useAssignmentActive,
  useCreateAssignment,
  useUpdateAssignment,
  type PayUnit,
  type SettlementPolicy,
} from "../assignment-api";
import { endText } from "../labels";

const dot = (d: string) => d.replaceAll("-", ".");
const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;

const POLICIES = [
  { value: "ACTUAL_DURATION", label: "실제 진행 시간" },
  { value: "STUDENT_REQUEST", label: "신청 시간" },
] as const satisfies readonly { value: SettlementPolicy; label: string }[];
const UNITS = [
  { value: "HOURLY", label: "시간당" },
  { value: "PER_SESSION", label: "세션당" },
] as const satisfies readonly { value: PayUnit; label: string }[];

const HELP = {
  start: "기수 기간 안의 날짜여야 해요.",
  end: "비우면 종료일 없이 이어져요. 종료일이 지나면 다음 날 00:00에 배정이 자동으로 끝나요.",
  policy: "실제 진행 시간은 멘토가 기록한 진행 시간으로, 신청 시간은 수강생이 신청한 시간으로 정산해요.",
};

/** 배정 패널 (F85·F68): `assignmentId`가 new면 추가 */
export function AssignmentSheet({
  mentor,
  assignmentId,
  canManage,
  onOpen,
  onClose,
}: {
  mentor: MentorItem;
  assignmentId: string;
  canManage: boolean;
  onOpen: (id: string) => void;
  onClose: () => void;
}) {
  const list = useQuery(mentorAssignmentsQuery(mentor.id));
  const access = useQuery(staffAccessQuery);
  const cohorts = access.data?.cohorts ?? [];
  const assignment = list.data?.find((a) => a.id === assignmentId);
  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined} className="w-120">
        {assignmentId === "new" ? (
          <AssignmentForm
            mentor={mentor}
            cohorts={cohorts}
            existing={list.data ?? []}
            onDone={onOpen}
            onClose={onClose}
          />
        ) : list.isPending ? (
          <>
            <PanelHead title="배정" description="" onClose={onClose} />
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          </>
        ) : !assignment ? (
          <>
            <PanelHead title="배정" description="" onClose={onClose} />
            <ErrorState className="m-6" onRetry={() => void list.refetch()} />
          </>
        ) : (
          <AssignmentView
            mentor={mentor}
            assignment={assignment}
            cohort={cohorts.find((c) => c.id === assignment.cohort_id)}
            canManage={canManage}
            onClose={onClose}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}

const statusBadge = (a: MentorAssignment) => (
  <Badge variant={a.is_active ? "success" : "secondary"}>{a.is_active ? "배정 중" : "종료"}</Badge>
);

function CohortRows({ assignment: a, cohort }: { assignment: MentorAssignment; cohort?: StaffCohort }) {
  return (
    <PanelSection title="기수">
      <PanelRow label="과정">{a.bootcamp_name}</PanelRow>
      <PanelRow label="기수">{a.cohort_number}기</PanelRow>
      {cohort ? (
        <>
          <PanelRow label="기수 기간">
            {dot(cohort.start_date)} ~ {dot(cohort.end_date)}
          </PanelRow>
          <PanelRow label="기수 상태">
            {COHORT_STATUS[cohort.status as keyof typeof COHORT_STATUS]?.label ?? cohort.status}
          </PanelRow>
        </>
      ) : null}
    </PanelSection>
  );
}

function AssignmentView({
  mentor,
  assignment: a,
  cohort,
  canManage,
  onClose,
}: {
  mentor: MentorItem;
  assignment: MentorAssignment;
  cohort?: StaffCohort;
  canManage: boolean;
  onClose: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const active = useAssignmentActive(mentor.id, a.cohort_id, a.id);
  const title = `${a.bootcamp_name} ${a.cohort_number}기`;
  const sub = `${mentor.name} · ${dot(a.start_date)} ~ ${a.end_date ? dot(a.end_date) : "종료일 없음"}`;
  if (editing)
    return (
      <AssignmentEdit
        mentor={mentor}
        assignment={a}
        cohort={cohort}
        title={title}
        sub={sub}
        onDone={() => setEditing(false)}
      />
    );
  const reactivate = async () => {
    try {
      await active.mutateAsync(true);
      toast.success(`${title} 배정을 다시 켰어요`);
    } catch (e) {
      toast.error(assignmentError(e));
    }
  };
  const end = endText(a);
  return (
    <>
      <PanelHead
        title={title}
        description={sub}
        badges={statusBadge(a)}
        actions={
          canManage ? (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                수정
              </Button>
              {a.is_active ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="border-destructive-text text-destructive-text hover:bg-destructive-subtle hover:text-destructive-text"
                  onClick={() => setConfirming(true)}
                >
                  배정 종료
                </Button>
              ) : (
                <Button variant="outline" size="sm" disabled={active.isPending} onClick={() => void reactivate()}>
                  다시 켜기
                </Button>
              )}
            </div>
          ) : null
        }
        onClose={onClose}
      />
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
        <CohortRows assignment={a} cohort={cohort} />
        <PanelSection title="기간">
          <PanelRow label="시작일" help={HELP.start}>
            {dot(a.start_date)}
          </PanelRow>
          <PanelRow label="종료일" help={HELP.end}>
            {a.end_date ? dot(a.end_date) : "종료일 없음"}
          </PanelRow>
        </PanelSection>
        <PanelSection title="정산 조건">
          <PanelRow label="정산 기준" help={HELP.policy}>
            {POLICIES.find((p) => p.value === a.cost_settlement_policy)?.label}
          </PanelRow>
          <PanelRow label="단가 기준">{UNITS.find((u) => u.value === a.pay_unit)?.label}</PanelRow>
          <PanelRow label="단가">{won(a.pay_rate)}</PanelRow>
          <PanelRow label="노쇼 1건">{a.no_show_pay_amount > 0 ? won(a.no_show_pay_amount) : "없음"}</PanelRow>
        </PanelSection>
        {end ? (
          <PanelSection title="종료">
            <PanelRow label="사유">{end.split(" · ")[0]}</PanelRow>
            <PanelRow label="종료 시각">
              {a.deactivated_at ? formatKst(a.deactivated_at, "yyyy.MM.dd HH:mm") : "—"}
            </PanelRow>
          </PanelSection>
        ) : null}
      </div>
      {confirming ? (
        <EndDialog mentor={mentor} assignment={a} title={title} onClose={() => setConfirming(false)} />
      ) : null}
    </>
  );
}

function EndDialog({
  mentor,
  assignment: a,
  title,
  onClose,
}: {
  mentor: MentorItem;
  assignment: MentorAssignment;
  title: string;
  onClose: () => void;
}) {
  const active = useAssignmentActive(mentor.id, a.cohort_id, a.id);
  const submit = async () => {
    try {
      const canceled = await active.mutateAsync(false);
      toast.success(
        canceled > 0 ? `배정을 종료했어요. 대기 중인 신청 ${canceled}건을 취소했어요` : "배정을 종료했어요",
      );
      onClose();
    } catch (e) {
      toast.error(assignmentError(e));
    }
  };
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-110 flex-col gap-4 p-6">
        <DialogTitle className="text-h2 text-foreground">{title} 배정을 종료할까요?</DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          {mentor.name} 멘토는 이 기수의 새 신청을 받지 않고, 대기 중인 신청은 자동으로 취소돼요. 이미 승인한 세션은
          그대로예요.
        </DialogDescription>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            돌아가기
          </Button>
          <Button variant="destructive" disabled={active.isPending} onClick={() => void submit()}>
            배정 종료
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ------------------------------------------------------------------ 폼
const amount = z
  .string()
  .trim()
  .regex(/^[0-9,]+$/, "숫자로 적어 주세요")
  .refine((v) => Number(v.replaceAll(",", "")) <= 100_000_000, "금액을 확인해 주세요");
const schema = z
  .object({
    bootcamp: z.string(),
    cohort: z.string(),
    start_date: z.string().min(1, "시작일을 골라 주세요"),
    end_date: z.string(),
    policy: z.enum(["ACTUAL_DURATION", "STUDENT_REQUEST"]),
    unit: z.enum(["HOURLY", "PER_SESSION"]),
    rate: amount,
    no_show: amount,
  })
  .refine((v) => !v.end_date || v.end_date >= v.start_date, {
    path: ["end_date"],
    message: "종료일은 시작일과 같거나 뒤여야 해요",
  });
type Values = z.infer<typeof schema>;
const num = (v: string) => Number(v.replaceAll(",", ""));

function Fields({ form, id }: { form: ReturnType<typeof useForm<Values>>; id: string }) {
  const { errors } = form.formState;
  const err = (name: keyof Values) =>
    errors[name] ? (
      <p className="mt-1 text-caption font-normal text-destructive-text">{errors[name]?.message}</p>
    ) : null;
  return (
    <>
      <PanelSection title="기간">
        <PanelRow label="시작일" htmlFor={`${id}-start`} help={HELP.start} top={!!errors.start_date}>
          <Input
            id={`${id}-start`}
            type="date"
            className="font-normal"
            aria-invalid={!!errors.start_date}
            {...form.register("start_date")}
          />
          {err("start_date")}
        </PanelRow>
        <PanelRow label="종료일" htmlFor={`${id}-end`} help={HELP.end} top={!!errors.end_date}>
          <Input
            id={`${id}-end`}
            type="date"
            className="font-normal"
            aria-invalid={!!errors.end_date}
            {...form.register("end_date")}
          />
          {err("end_date")}
        </PanelRow>
      </PanelSection>
      <PanelSection title="정산 조건">
        <PanelRow label="정산 기준" help={HELP.policy}>
          <Controller
            control={form.control}
            name="policy"
            render={({ field }) => (
              <Segmented label="정산 기준" value={field.value} onChange={field.onChange} options={POLICIES} />
            )}
          />
        </PanelRow>
        <PanelRow label="단가 기준">
          <Controller
            control={form.control}
            name="unit"
            render={({ field }) => (
              <Segmented label="단가 기준" value={field.value} onChange={field.onChange} options={UNITS} />
            )}
          />
        </PanelRow>
        <PanelRow label="단가" htmlFor={`${id}-rate`} top={!!errors.rate}>
          <Input
            id={`${id}-rate`}
            inputMode="numeric"
            className="font-normal"
            aria-invalid={!!errors.rate}
            {...form.register("rate")}
          />
          {err("rate")}
        </PanelRow>
        <PanelRow label="노쇼 1건" htmlFor={`${id}-noshow`} top={!!errors.no_show}>
          <Input
            id={`${id}-noshow`}
            inputMode="numeric"
            className="font-normal"
            aria-invalid={!!errors.no_show}
            {...form.register("no_show")}
          />
          {err("no_show")}
        </PanelRow>
      </PanelSection>
    </>
  );
}

function Footer({ onCancel, submitLabel, pending }: { onCancel: () => void; submitLabel: string; pending: boolean }) {
  return (
    <div className="flex justify-end gap-2 border-t border-border px-6 py-3">
      <Button type="button" variant="outline" onClick={onCancel}>
        취소
      </Button>
      <Button type="submit" disabled={pending}>
        {submitLabel}
      </Button>
    </div>
  );
}

function AssignmentEdit({
  mentor,
  assignment: a,
  cohort,
  title,
  sub,
  onDone,
}: {
  mentor: MentorItem;
  assignment: MentorAssignment;
  cohort?: StaffCohort;
  title: string;
  sub: string;
  onDone: () => void;
}) {
  const id = useId();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      bootcamp: "",
      cohort: a.cohort_id,
      start_date: a.start_date,
      end_date: a.end_date ?? "",
      policy: a.cost_settlement_policy,
      unit: a.pay_unit,
      rate: a.pay_rate.toLocaleString("ko-KR"),
      no_show: a.no_show_pay_amount.toLocaleString("ko-KR"),
    },
  });
  const save = useUpdateAssignment(mentor.id, a.cohort_id, a.id);
  const [error, setError] = useState<string | null>(null);
  const dirty = form.formState.isDirty;
  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !save.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await save.mutateAsync({
        start_date: v.start_date,
        end_date: v.end_date || null,
        cost_settlement_policy: v.policy,
        pay_unit: v.unit,
        pay_rate: num(v.rate),
        no_show_pay_amount: num(v.no_show),
      });
      form.reset(v);
      toast.success(`${title} 배정을 저장했어요`);
      onDone();
    } catch (e) {
      setError(assignmentError(e));
    }
  });
  return (
    <>
      <PanelHead
        title={title}
        description={sub}
        badges={
          <>
            {statusBadge(a)}
            <Badge variant="warning">수정 중</Badge>
          </>
        }
        onClose={onDone}
      />
      <form
        aria-label="배정 수정"
        noValidate
        onSubmit={(e) => void onSubmit(e)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
          <CohortRows assignment={a} cohort={cohort} />
          <Fields form={form} id={id} />
          {error ? <Alert variant="error" title={error} /> : null}
        </div>
        <Footer onCancel={onDone} submitLabel="저장" pending={save.isPending} />
        <DiscardDialog blocker={blocker} />
      </form>
    </>
  );
}

function AssignmentForm({
  mentor,
  cohorts,
  existing,
  onDone,
  onClose,
}: {
  mentor: MentorItem;
  cohorts: StaffCohort[];
  existing: MentorAssignment[];
  onDone: (id: string) => void;
  onClose: () => void;
}) {
  const id = useId();
  const form = useForm<Values>({
    resolver: zodResolver(schema.refine((v) => !!v.cohort, { path: ["cohort"], message: "기수를 골라 주세요" })),
    defaultValues: {
      bootcamp: "",
      cohort: "",
      start_date: "",
      end_date: "",
      policy: "ACTUAL_DURATION",
      unit: "HOURLY",
      rate: "",
      no_show: "0",
    },
  });
  const create = useCreateAssignment(mentor.id);
  const [error, setError] = useState<string | null>(null);
  const bootcamp = useWatch({ control: form.control, name: "bootcamp" });
  const cohortId = useWatch({ control: form.control, name: "cohort" });
  const activeCohorts = new Set(existing.filter((a) => a.is_active).map((a) => a.cohort_id));
  const bootcamps = [...new Map(cohorts.map((c) => [c.bootcamp_id, c.bootcamp_name])).entries()];
  const inBootcamp = cohorts.filter((c) => c.bootcamp_id === bootcamp);
  const picked = cohorts.find((c) => c.id === cohortId);
  const dirty = form.formState.isDirty;
  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !create.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });
  const { errors } = form.formState;
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      const saved = await create.mutateAsync({
        cohortId: v.cohort,
        body: {
          mentor_id: mentor.id,
          start_date: v.start_date,
          end_date: v.end_date || null,
          cost_settlement_policy: v.policy,
          pay_unit: v.unit,
          pay_rate: num(v.rate),
          no_show_pay_amount: num(v.no_show),
        },
      });
      form.reset(v);
      toast.success(`${picked ? `${picked.bootcamp_name} ${picked.cohort_number}기에` : ""} 배정했어요`);
      onDone(saved.id);
    } catch (e) {
      setError(assignmentError(e));
    }
  });
  return (
    <>
      <PanelHead title="배정 추가" description={mentor.name} onClose={onClose} />
      <form
        aria-label="배정 추가"
        noValidate
        onSubmit={(e) => void onSubmit(e)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
          <PanelSection title="기수">
            <PanelRow label="과정" htmlFor={`${id}-bootcamp`}>
              <Controller
                control={form.control}
                name="bootcamp"
                render={({ field }) => (
                  <Select
                    value={field.value}
                    onValueChange={(v) => {
                      field.onChange(v);
                      form.setValue("cohort", "", { shouldDirty: true });
                    }}
                  >
                    <SelectTrigger id={`${id}-bootcamp`} aria-label="과정" className="font-normal">
                      <SelectValue placeholder="과정 고르기" />
                    </SelectTrigger>
                    <SelectContent>
                      {bootcamps.map(([bid, name]) => (
                        <SelectItem key={bid} value={bid}>
                          {name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </PanelRow>
            {bootcamp ? (
              <PanelRow label="기수" htmlFor={`${id}-cohort`} top={!!errors.cohort}>
                <Controller
                  control={form.control}
                  name="cohort"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id={`${id}-cohort`} aria-label="기수" className="font-normal">
                        <SelectValue placeholder="기수 고르기" />
                      </SelectTrigger>
                      <SelectContent>
                        {inBootcamp.map((c) => (
                          <SelectItem key={c.id} value={c.id} disabled={activeCohorts.has(c.id)}>
                            {`${c.cohort_number}기 · ${dot(c.start_date)} ~ ${dot(c.end_date)}${activeCohorts.has(c.id) ? " · 배정 중" : ""}`}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                {errors.cohort ? (
                  <p className="mt-1 text-caption font-normal text-destructive-text">{errors.cohort.message}</p>
                ) : null}
              </PanelRow>
            ) : null}
          </PanelSection>
          <Fields form={form} id={id} />
          {error ? <Alert variant="error" title={error} /> : null}
        </div>
        <Footer onCancel={onClose} submitLabel="추가" pending={create.isPending} />
        <DiscardDialog blocker={blocker} />
      </form>
    </>
  );
}
