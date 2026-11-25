import { zodResolver } from "@hookform/resolvers/zod";
import { useBlocker } from "@tanstack/react-router";
import { X } from "lucide-react";
import { useId, useMemo, useState, type ReactNode } from "react";
import { Controller, useForm, useWatch, type UseFormReturn } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { withAllCohorts } from "@/features/admin-staff-registrations/api";
import { EMPLOYMENT_TYPE_LABELS } from "@/features/auth/messages";
import { bootcampCohorts, NO_TEAM, scopeOf, teamsOf, type StaffOptions } from "@/features/auth/staff-api";
import { staffFormValues } from "@/features/auth/staff-form";
import { hasPermission, type StaffAccess } from "@/features/staff/api";
import { cn } from "@/lib/utils";

import { assignmentName, DATA_SCOPE_LABELS, useUpdateEmployee, type Employee } from "../api";
import { employeeFormSchema as schema, payload, type Editable, type EmployeeFormValues as Values } from "../form";
import { NO_TEAM_LABEL } from "../groups";

const SCOPE_TITLES = { COURSE: "담당 과정", COHORT: "담당 기수" } as const;
const SUPER_ADMIN_HELP = "최고 관리자는 직위와 상관없이 모든 권한과 모든 데이터를 볼 수 있어요.";
const superAdminLabel = (on: boolean) => (on ? "지정됨" : "지정 안 됨");

/** 직원 상세·수정 슬라이드 패널 (F67). 수정은 같은 패널에서 조회와 같은 섹션·줄 구성으로 한다 */
export function EmployeeSheet({
  employee,
  options,
  access,
  onClose,
}: {
  employee: Employee;
  options: StaffOptions;
  access: StaffAccess;
  onClose: () => void;
}) {
  const editable: Editable = {
    org: hasPermission(access, "org.employee.manage"),
    assign: hasPermission(access, "staff.assignment.manage"),
    superAdmin: access.is_super_admin,
  };
  const canEdit = editable.org || editable.assign || editable.superAdmin;
  const [editing, setEditing] = useState(false);
  const name = employee.user?.name ?? "직원";

  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined}>
        <div className="flex items-start gap-3 border-b border-border py-5 pr-4 pl-6">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <SheetTitle className="text-h2 text-foreground">{name}</SheetTitle>
              {employee.is_super_admin ? <Badge variant="primary">최고 관리자</Badge> : null}
              {editing ? <Badge variant="info">수정 중</Badge> : null}
            </div>
            <SheetDescription className="truncate text-body text-muted-foreground">
              {employee.user?.email ?? "—"}
            </SheetDescription>
          </div>
          {canEdit && !editing ? (
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              수정
            </Button>
          ) : null}
          <Button variant="ghost" size="sm" aria-label="닫기" className="px-2" onClick={onClose}>
            <X />
          </Button>
        </div>
        {editing ? (
          <EmployeeForm
            employee={employee}
            options={options}
            access={access}
            editable={editable}
            onDone={() => setEditing(false)}
          />
        ) : (
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
            <EmployeeView employee={employee} options={options} />
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="shrink-0 overflow-hidden rounded-lg border border-border">
      <h3 id={id} className="border-b border-border bg-muted px-3.5 py-2.5 text-body-strong text-foreground">
        {title}
      </h3>
      <div className="flex flex-col gap-2.5 p-3.5">{children}</div>
    </section>
  );
}

/** '라벨 | 값' 한 줄 */
function Row({ label, children, htmlFor }: { label: string; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="grid grid-cols-[88px_minmax(0,1fr)] items-center gap-3">
      {htmlFor ? (
        <label htmlFor={htmlFor} className="text-body text-muted-foreground">
          {label}
        </label>
      ) : (
        <span className="text-body text-muted-foreground">{label}</span>
      )}
      <div className="min-w-0 text-body-strong text-foreground">{children}</div>
    </div>
  );
}

function names(options: StaffOptions, e: Pick<Employee, "department_id" | "team_id" | "position_id">) {
  return {
    department: options.departments.find((d) => d.id === e.department_id)?.name ?? "—",
    team: e.team_id ? (options.teams.find((t) => t.id === e.team_id)?.name ?? "—") : NO_TEAM_LABEL,
    position: options.positions.find((p) => p.id === e.position_id)?.name ?? "—",
  };
}

function EmployeeView({ employee, options }: { employee: Employee; options: StaffOptions }) {
  const n = names(options, employee);
  const scope = scopeOf(options, employee.position_id);
  const assignments = employee.assignments ?? [];
  return (
    <>
      <Section title="소속">
        <Row label="부서">{n.department}</Row>
        <Row label="팀">{n.team}</Row>
        <Row label="고용 형태">{EMPLOYMENT_TYPE_LABELS[employee.employment_type] ?? employee.employment_type}</Row>
      </Section>
      <Section title="직위·권한">
        <Row label="직위">{n.position}</Row>
        <Row label="데이터 범위">{DATA_SCOPE_LABELS[employee.data_scope]}</Row>
      </Section>
      {scope ? (
        <Section title={SCOPE_TITLES[scope]}>
          {assignments.length ? (
            <ul aria-label={SCOPE_TITLES[scope]} className="flex flex-wrap gap-1.5">
              {assignments.map((a) => (
                <li key={a.staff_id}>
                  <Badge variant="secondary">{assignmentName(a)}</Badge>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-body text-muted-foreground">담당이 없어요.</p>
          )}
        </Section>
      ) : null}
      <Section title="최고 관리자">
        <Row label="지정 여부">{superAdminLabel(employee.is_super_admin)}</Row>
        <p className="text-caption text-muted-foreground">{SUPER_ADMIN_HELP}</p>
      </Section>
    </>
  );
}

function errorText(e: unknown): string {
  return e instanceof ApiError ? e.message : "저장하지 못했어요. 잠시 후 다시 시도해 주세요.";
}

function EmployeeForm({
  employee,
  options: baseOptions,
  access,
  editable,
  onDone,
}: {
  employee: Employee;
  options: StaffOptions;
  access: StaffAccess;
  editable: Editable;
  onDone: () => void;
}) {
  // 지금 담당 기수는 다른 직원이 고를 수 없는 기수라 선택지에 없으니 담당 기수로 보충한다 (A63)
  const options = useMemo(() => {
    const current = employee.assignments?.find((a) => a.cohort_id)?.cohort_id;
    return withAllCohorts(
      baseOptions,
      access.cohorts.filter((c) => c.id === current),
    );
  }, [baseOptions, access.cohorts, employee.assignments]);
  const initial = useMemo<Values>(
    () => ({
      ...staffFormValues(options, {
        department_id: employee.department_id,
        team_id: employee.team_id,
        position_id: employee.position_id,
        employment_type: employee.employment_type,
        assignments: (employee.assignments ?? []).map((a) => ({ bootcamp_id: a.bootcamp_id, cohort_id: a.cohort_id })),
      }),
      is_super_admin: employee.is_super_admin,
    }),
    [options, employee],
  );
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: initial });
  const update = useUpdateEmployee(employee.id);
  const [error, setError] = useState<string | null>(null);
  const dirty = form.formState.isDirty;

  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !update.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    const body = payload(options, initial, v, editable);
    if (Object.keys(body).length === 0) return onDone();
    try {
      await update.mutateAsync(body);
      form.reset(v);
      toast.success(`${employee.user?.name ?? "직원"}님 정보를 저장했어요`);
      onDone();
    } catch (e) {
      setError(errorText(e));
    }
  });

  return (
    <form aria-label="직원 수정" noValidate onSubmit={(e) => void onSubmit(e)} className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
        <FormSections form={form} options={options} employee={employee} editable={editable} />
        {error ? <Alert variant="error" title={error} /> : null}
      </div>
      <div className="flex justify-end gap-2 border-t border-border px-6 py-3">
        <Button type="button" variant="outline" onClick={onDone}>
          취소
        </Button>
        <Button type="submit" disabled={update.isPending}>
          저장
        </Button>
      </div>
      <Dialog open={blocker.status === "blocked"} onOpenChange={(open) => (open ? undefined : blocker.reset?.())}>
        <DialogContent className="flex max-w-110 flex-col gap-4 p-6">
          <DialogTitle className="text-h2 text-foreground">저장하지 않은 변경이 있어요</DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            닫으면 고친 내용이 사라져요.
          </DialogDescription>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => blocker.reset?.()}>
              계속 고치기
            </Button>
            <Button variant="destructive" onClick={() => blocker.proceed?.()}>
              버리고 닫기
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </form>
  );
}

function FormSections({
  form,
  options,
  employee,
  editable,
}: {
  form: UseFormReturn<Values>;
  options: StaffOptions;
  employee: Employee;
  editable: Editable;
}) {
  const id = useId();
  const { errors } = form.formState;
  const [departmentId, positionId, cohortBootcampId, cohortId, superAdmin] = useWatch({
    control: form.control,
    name: ["department_id", "position_id", "cohort_bootcamp_id", "cohort_id", "is_super_admin"],
  });
  const n = names(options, employee);
  const scope = positionId ? scopeOf(options, positionId) : null;
  const clearAssignments = () => {
    form.setValue("bootcamp_ids", [], { shouldDirty: true });
    form.setValue("cohort_bootcamp_id", "", { shouldDirty: true });
    form.setValue("cohort_id", "", { shouldDirty: true });
  };
  const bootcamps = [...options.bootcamps].sort((a, b) => a.name.localeCompare(b.name, "ko"));
  const currentCohort = employee.assignments?.find((a) => a.cohort_id);

  return (
    <>
      <Section title="소속">
        {editable.org ? (
          <>
            <SelectRow
              form={form}
              name="department_id"
              label="부서"
              id={`${id}-department`}
              items={[...options.departments]
                .sort((a, b) => a.name.localeCompare(b.name, "ko"))
                .map((d) => ({ value: d.id, label: d.name }))}
              onChange={() => form.setValue("team_id", "", { shouldDirty: true })}
            />
            <SelectRow
              form={form}
              name="team_id"
              label="팀"
              id={`${id}-team`}
              placeholder="팀을 선택하세요"
              error={errors.team_id?.message}
              items={[
                ...teamsOf(options, departmentId).map((t) => ({ value: t.id, label: t.name })),
                { value: NO_TEAM, label: NO_TEAM_LABEL },
              ]}
            />
            <SelectRow
              form={form}
              name="employment_type"
              label="고용 형태"
              id={`${id}-employment`}
              items={options.employment_types.map((t) => ({ value: t, label: EMPLOYMENT_TYPE_LABELS[t] ?? t }))}
            />
          </>
        ) : (
          <>
            <Row label="부서">{n.department}</Row>
            <Row label="팀">{n.team}</Row>
            <Row label="고용 형태">{EMPLOYMENT_TYPE_LABELS[employee.employment_type] ?? employee.employment_type}</Row>
          </>
        )}
      </Section>
      <Section title="직위·권한">
        {editable.org ? (
          <SelectRow
            form={form}
            name="position_id"
            label="직위"
            id={`${id}-position`}
            items={options.positions.map((p) => ({ value: p.id, label: p.name }))}
            onChange={clearAssignments}
          />
        ) : (
          <Row label="직위">{n.position}</Row>
        )}
        <Row label="데이터 범위">
          {positionId === employee.position_id ? (
            DATA_SCOPE_LABELS[employee.data_scope]
          ) : (
            <span className="text-body text-muted-foreground">저장하면 바뀐 직위의 범위를 따라요</span>
          )}
        </Row>
        {editable.org ? (
          <p className="text-caption text-muted-foreground">
            데이터 범위는 직위에 따라 정해져요. 직위를 바꾸면 담당 방식이 달라져 담당을 다시 골라야 할 수 있어요.
          </p>
        ) : null}
      </Section>
      {scope === "COURSE" ? (
        <Section title={SCOPE_TITLES.COURSE}>
          <CourseField form={form} bootcamps={bootcamps} editable={editable.assign} employee={employee} />
          {errors.bootcamp_ids?.message ? (
            <p className="text-caption text-destructive-text">{errors.bootcamp_ids.message}</p>
          ) : null}
        </Section>
      ) : null}
      {scope === "COHORT" ? (
        <Section title={SCOPE_TITLES.COHORT}>
          {editable.assign ? (
            <>
              <SelectRow
                form={form}
                name="cohort_bootcamp_id"
                label="과정"
                id={`${id}-cohort-bootcamp`}
                placeholder="과정을 선택하세요"
                items={bootcamps.map((b) => ({ value: b.id, label: b.name }))}
                onChange={() => form.setValue("cohort_id", "", { shouldDirty: true })}
              />
              <SelectRow
                form={form}
                name="cohort_id"
                label="기수"
                id={`${id}-cohort`}
                placeholder={cohortBootcampId ? "기수를 선택하세요" : "과정을 먼저 고르세요"}
                disabled={!cohortBootcampId}
                items={bootcampCohorts(options, cohortBootcampId).map((c) => ({
                  value: c.id,
                  label: `${c.cohort_number}기`,
                }))}
              />
              {currentCohort && !cohortId && positionId === employee.position_id ? (
                <p className="text-caption text-muted-foreground">지금 담당: {assignmentName(currentCohort)}</p>
              ) : null}
            </>
          ) : (
            <Row label="기수">
              {(employee.assignments ?? []).map(assignmentName).join(", ") || (
                <span className="text-body text-muted-foreground">없음</span>
              )}
            </Row>
          )}
        </Section>
      ) : null}
      <Section title="최고 관리자">
        {editable.superAdmin ? (
          <Row label="지정 여부" htmlFor={`${id}-super`}>
            <span className="flex h-9 items-center gap-2.5">
              <Switch
                id={`${id}-super`}
                aria-label="최고 관리자"
                checked={superAdmin}
                onCheckedChange={(on) => form.setValue("is_super_admin", on, { shouldDirty: true })}
              />
              <span aria-hidden>{superAdminLabel(superAdmin)}</span>
            </span>
          </Row>
        ) : (
          <Row label="지정 여부">{superAdminLabel(employee.is_super_admin)}</Row>
        )}
        <p className="text-caption text-muted-foreground">
          {SUPER_ADMIN_HELP}
          {editable.superAdmin ? null : " 최고 관리자만 바꿀 수 있어요."}
        </p>
      </Section>
    </>
  );
}

type SelectName = "department_id" | "team_id" | "position_id" | "employment_type" | "cohort_bootcamp_id" | "cohort_id";

function SelectRow({
  form,
  name,
  label,
  id,
  items,
  placeholder = "선택하세요",
  error,
  disabled,
  onChange,
}: {
  form: UseFormReturn<Values>;
  name: SelectName;
  label: string;
  id: string;
  items: { value: string; label: string }[];
  placeholder?: string;
  error?: string | undefined;
  disabled?: boolean;
  onChange?: () => void;
}) {
  return (
    <Row label={label} htmlFor={id}>
      <Controller
        control={form.control}
        name={name}
        render={({ field }) => (
          <Select
            value={field.value}
            disabled={disabled}
            onValueChange={(value) => {
              if (value === field.value) return;
              field.onChange(value);
              onChange?.();
            }}
          >
            <SelectTrigger id={id} aria-invalid={error ? true : undefined} className="font-normal">
              <SelectValue placeholder={placeholder} />
            </SelectTrigger>
            <SelectContent>
              {items.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      />
      {error ? <p className="mt-1 text-caption font-normal text-destructive-text">{error}</p> : null}
    </Row>
  );
}

/** 과정 담당: 고른 과정을 칩으로, 드롭다운에서 더한다 */
function CourseField({
  form,
  bootcamps,
  editable,
  employee,
}: {
  form: UseFormReturn<Values>;
  bootcamps: StaffOptions["bootcamps"];
  editable: boolean;
  employee: Employee;
}) {
  if (!editable) {
    const items = employee.assignments ?? [];
    return items.length ? (
      <ul aria-label="담당 과정" className="flex flex-wrap gap-1.5">
        {items.map((a) => (
          <li key={a.staff_id}>
            <Badge variant="secondary">{assignmentName(a)}</Badge>
          </li>
        ))}
      </ul>
    ) : (
      <p className="text-body text-muted-foreground">담당이 없어요.</p>
    );
  }
  return (
    <Controller
      control={form.control}
      name="bootcamp_ids"
      render={({ field }) => {
        // 선택지에 없는 과정(보관 등)도 직원 응답의 이름으로 보인다
        const chosen = field.value.map((id) => ({
          id,
          name:
            bootcamps.find((b) => b.id === id)?.name ??
            employee.assignments?.find((a) => a.bootcamp_id === id)?.bootcamp_name ??
            "—",
        }));
        const remaining = bootcamps.filter((b) => !field.value.includes(b.id));
        return (
          <>
            {chosen.length ? (
              <ul aria-label="담당 과정" className="flex flex-wrap gap-1.5">
                {chosen.map((b) => (
                  <li
                    key={b.id}
                    className="inline-flex items-center gap-1 rounded-full bg-muted py-0.5 pr-1 pl-2.5 text-caption-strong text-foreground"
                  >
                    {b.name}
                    <button
                      type="button"
                      aria-label={`${b.name} 빼기`}
                      className="inline-flex size-5 items-center justify-center rounded-full hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                      onClick={() => field.onChange(field.value.filter((id) => id !== b.id))}
                    >
                      <X aria-hidden className="size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-body text-muted-foreground">담당이 없어요.</p>
            )}
            <Select value="" onValueChange={(id) => field.onChange([...field.value, id])} disabled={!remaining.length}>
              <SelectTrigger aria-label="담당 과정 추가" className={cn("font-normal")}>
                <SelectValue placeholder={remaining.length ? "담당 과정 추가" : "모든 과정을 추가했어요"} />
              </SelectTrigger>
              <SelectContent>
                {remaining.map((b) => (
                  <SelectItem key={b.id} value={b.id}>
                    {b.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        );
      }}
    />
  );
}
