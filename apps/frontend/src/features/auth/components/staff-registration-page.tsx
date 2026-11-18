import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { LogOut, Pencil, Plus, RotateCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Controller, useFieldArray, useForm, useWatch, type Control } from "react-hook-form";
import { z } from "zod";

import { ApiError } from "@/api/errors";
import { FormField } from "@/components/form-field";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { formatKst } from "@/lib/datetime";

import { logout, meQuery, type Me } from "../api";
import { EMPLOYMENT_TYPE_LABELS, STAFF_ROLE_LABELS } from "../messages";
import { homePath } from "../navigation";
import {
  departmentLabels,
  fromTargetValue,
  staffKeys,
  staffOptionsQuery,
  staffRegistrationQuery,
  submitStaffRegistration,
  targetOptions,
  toTargetValue,
  type StaffOptions,
  type StaffRegistration,
} from "../staff-api";

const MAX_ASSIGNMENTS = 20;

/**
 * 운영진 최초 정보 입력 (Figma `정보 입력`·`승인 대기`·`반려`, decisions A11·F11·F25).
 * 처음이면 입력 폼, 신청했으면 승인 대기(수정 가능), 반려면 사유와 함께 다시 신청.
 */
export function StaffRegistrationPage({ me }: { me: Me }) {
  const options = useQuery(staffOptionsQuery);
  const registration = useQuery(staffRegistrationQuery);
  const [editing, setEditing] = useState(false);

  if (!options.data || registration.isPending) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    );
  }
  const reg = registration.data ?? null;
  return (
    <div className="flex flex-col gap-6">
      <Account me={me} />
      {reg === null || editing ? (
        <RegistrationForm options={options.data} initial={reg} onSubmitted={() => setEditing(false)} />
      ) : (
        <RegistrationStatus options={options.data} registration={reg} onEdit={() => setEditing(true)} />
      )}
    </div>
  );
}

function Account({ me }: { me: Me }) {
  const navigate = useNavigate();
  return (
    <div className="flex items-center gap-2">
      <span
        aria-hidden
        className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-accent text-caption-strong text-accent-foreground"
      >
        {me.name.slice(0, 1)}
      </span>
      <span className="min-w-0 flex-1 truncate text-body-sm text-muted-foreground">{me.email}</span>
      <Button
        variant="ghost"
        size="sm"
        onClick={async () => {
          await logout();
          await navigate({ to: "/staff/login", replace: true });
        }}
      >
        <LogOut />
        로그아웃
      </Button>
    </div>
  );
}

const schema = z.object({
  department_id: z.string().min(1, "부서를 골라 주세요."),
  position_id: z.string().min(1, "직위를 골라 주세요."),
  employment_type: z.string().min(1, "고용 형태를 골라 주세요."),
  assignments: z
    .array(z.object({ role: z.enum(["MANAGER", "ASSISTANT"]), target: z.string().min(1, "대상을 골라 주세요.") }))
    .max(MAX_ASSIGNMENTS)
    .superRefine((rows, ctx) => {
      const seen = new Set<string>();
      rows.forEach((row, index) => {
        const key = `${row.role}:${row.target}`;
        if (row.target && seen.has(key)) {
          ctx.addIssue({ code: "custom", path: [index, "target"], message: "같은 담당을 두 번 골랐어요." });
        }
        seen.add(key);
      });
    }),
});
type Values = z.infer<typeof schema>;

function RegistrationForm({
  options,
  initial,
  onSubmitted,
}: {
  options: StaffOptions;
  initial: StaffRegistration | null;
  onSubmitted: () => void;
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      department_id: initial?.department_id ?? "",
      position_id: initial?.position_id ?? "",
      employment_type: initial?.employment_type ?? "",
      assignments: (initial?.assignments ?? []).map((a) => ({ role: a.role, target: toTargetValue(a) })),
    },
  });
  const rows = useFieldArray({ control: form.control, name: "assignments" });
  const { errors, isSubmitting } = form.formState;
  const departments = departmentLabels(options.departments);

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const saved = await submitStaffRegistration({
        department_id: values.department_id,
        position_id: values.position_id,
        employment_type: values.employment_type as StaffRegistration["employment_type"],
        assignments: values.assignments.map((a) => ({ role: a.role, ...fromTargetValue(a.target) })),
      });
      queryClient.setQueryData(staffKeys.mine, saved);
      onSubmitted();
    } catch (err) {
      if (err instanceof ApiError) {
        for (const [field, message] of Object.entries(err.fieldErrors)) {
          form.setError(field as keyof Values, { message });
        }
        setError(err.message);
        return;
      }
      setError("잠시 후 다시 시도해 주세요.");
    }
  });

  return (
    <>
      <div className="flex flex-col gap-1.5">
        <h1 className="text-h2 text-foreground">운영진 정보 입력</h1>
        <p className="text-body-sm text-muted-foreground">
          처음 로그인하셨네요. 소속과 담당을 입력하면 운영진이 확인한 뒤 승인해요.
        </p>
      </div>
      {error ? <Alert variant="error" title="신청하지 못했어요" description={error} /> : null}
      <form noValidate onSubmit={onSubmit} className="flex flex-col gap-6">
        <div className="grid gap-4 md:grid-cols-2">
          <SelectField
            control={form.control}
            name="department_id"
            label="부서"
            error={errors.department_id?.message}
            items={departments.map((d) => ({ value: d.id, label: d.label }))}
          />
          <SelectField
            control={form.control}
            name="position_id"
            label="직위"
            error={errors.position_id?.message}
            items={options.positions.map((p) => ({ value: p.id, label: p.name }))}
          />
          <SelectField
            control={form.control}
            name="employment_type"
            label="고용 형태"
            error={errors.employment_type?.message}
            items={options.employment_types.map((t) => ({ value: t, label: EMPLOYMENT_TYPE_LABELS[t] ?? t }))}
            className="md:col-span-2"
          />
        </div>

        <section aria-labelledby="assignments-label" className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span id="assignments-label" className="text-label text-foreground">
              담당 과정·기수
            </span>
            <span className="text-caption text-muted-foreground">
              {rows.fields.length} / {MAX_ASSIGNMENTS}
            </span>
          </div>
          <p className="text-caption text-muted-foreground">
            {rows.fields.length
              ? "운영 매니저는 과정 전체 또는 기수, 조교는 기수를 고르세요. 운영진이 승인할 때 조정할 수 있어요."
              : "담당 없이 신청할 수 있어요. 승인할 때 운영진이 정할 수 있어요."}
          </p>
          {rows.fields.map((row, index) => (
            <AssignmentRow
              key={row.id}
              index={index}
              control={form.control}
              options={options}
              error={errors.assignments?.[index]?.target?.message}
              onRemove={() => rows.remove(index)}
              onRoleChange={(role) => {
                // 조교로 바꾸면 과정 전체는 고를 수 없다
                if (role === "ASSISTANT" && form.getValues(`assignments.${index}.target`).startsWith("bootcamp:")) {
                  form.setValue(`assignments.${index}.target`, "");
                }
              }}
            />
          ))}
          <Button
            variant="outline"
            className="w-full"
            disabled={rows.fields.length >= MAX_ASSIGNMENTS}
            onClick={() => rows.append({ role: "MANAGER", target: "" })}
          >
            <Plus />
            담당 추가
          </Button>
        </section>

        <Button type="submit" disabled={isSubmitting} className="w-full">
          승인 신청
        </Button>
      </form>
    </>
  );
}

function SelectField({
  control,
  name,
  label,
  items,
  error,
  className,
}: {
  control: Control<Values>;
  name: "department_id" | "position_id" | "employment_type";
  label: string;
  items: { value: string; label: string }[];
  error: string | undefined;
  className?: string;
}) {
  return (
    <FormField label={label} error={error} {...(className ? { className } : {})}>
      {(field) => (
        <Controller
          control={control}
          name={name}
          render={({ field: selected }) => (
            <Select value={selected.value} onValueChange={selected.onChange}>
              <SelectTrigger {...field}>
                <SelectValue placeholder="골라 주세요" />
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
      )}
    </FormField>
  );
}

/** 담당 한 줄: 데스크톱은 역할·대상·삭제 한 줄, 태블릿·모바일은 '역할+삭제 / 대상' 두 줄 (F25) */
function AssignmentRow({
  index,
  control,
  options,
  error,
  onRemove,
  onRoleChange,
}: {
  index: number;
  control: Control<Values>;
  options: StaffOptions;
  error: string | undefined;
  onRemove: () => void;
  onRoleChange: (role: "MANAGER" | "ASSISTANT") => void;
}) {
  const role = useWatch({ control, name: `assignments.${index}.role` });
  const number = index + 1;
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border p-2 lg:flex-row lg:items-start">
      <div className="flex items-center gap-2 lg:w-40 lg:shrink-0">
        <Controller
          control={control}
          name={`assignments.${index}.role`}
          render={({ field }) => (
            <Select
              value={field.value}
              onValueChange={(v) => {
                field.onChange(v);
                onRoleChange(v as "MANAGER" | "ASSISTANT");
              }}
            >
              <SelectTrigger aria-label={`담당 ${number} 역할`} className="flex-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(["MANAGER", "ASSISTANT"] as const).map((r) => (
                  <SelectItem key={r} value={r}>
                    {STAFF_ROLE_LABELS[r]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
        <Button
          variant="ghost"
          size="sm"
          aria-label={`담당 ${number} 삭제`}
          onClick={onRemove}
          className="px-2 lg:hidden"
        >
          <Trash2 />
        </Button>
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <Controller
          control={control}
          name={`assignments.${index}.target`}
          render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger aria-label={`담당 ${number} 대상`} aria-invalid={error ? true : undefined}>
                <SelectValue placeholder="과정 또는 기수" />
              </SelectTrigger>
              <SelectContent>
                {targetOptions(options, role).map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
        {error ? <p className="text-caption text-destructive-text">{error}</p> : null}
      </div>
      <Button
        variant="ghost"
        size="sm"
        aria-label={`담당 ${number} 삭제`}
        onClick={onRemove}
        className="hidden px-2 lg:inline-flex"
      >
        <Trash2 />
      </Button>
    </div>
  );
}

function RegistrationStatus({
  options,
  registration,
  onEdit,
}: {
  options: StaffOptions;
  registration: StaffRegistration;
  onEdit: () => void;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [refreshing, setRefreshing] = useState(false);
  const rejected = registration.status === "REJECTED";
  const department = departmentLabels(options.departments).find((d) => d.id === registration.department_id)?.label;
  const position = options.positions.find((p) => p.id === registration.position_id)?.name;
  const targets = new Map([...targetOptions(options, "MANAGER")].map((t) => [t.value as string, t.label]));
  const at = rejected ? registration.reviewed_at : registration.created_at;

  /** 알림 없이 다시 조회만 한다. 승인됐으면 운영진 홈으로 (F25) */
  const refresh = async () => {
    setRefreshing(true);
    try {
      const me = await queryClient.fetchQuery({ ...meQuery, staleTime: 0 });
      if (me.approval_status === "APPROVED") {
        await navigate({ href: homePath(me), replace: true });
        return;
      }
      await queryClient.refetchQueries({ queryKey: staffKeys.mine });
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <>
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Badge variant={rejected ? "destructive" : "warning"}>{rejected ? "반려" : "승인 대기"}</Badge>
          {at ? (
            <span className="text-caption text-muted-foreground">
              {formatKst(at, "MM/dd HH:mm")} {rejected ? "처리" : "신청"}
            </span>
          ) : null}
        </div>
        <h1 className="text-h2 text-foreground">{rejected ? "신청이 반려됐어요" : "승인을 기다리고 있어요"}</h1>
        <p className="text-body-sm text-muted-foreground">
          {rejected
            ? "아래 사유를 확인하고 내용을 고쳐 다시 신청해 주세요."
            : "운영진이 신청 내용을 확인하고 있어요. 승인되면 이 화면을 새로고침하거나 다시 로그인해 주세요."}
        </p>
      </div>
      {rejected ? (
        <Alert variant="error" title="반려 사유" description={registration.reject_reason ?? "사유가 없어요."} />
      ) : null}
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 rounded-lg border border-border px-4 py-3 text-body-sm">
        <dt className="text-muted-foreground">부서</dt>
        <dd className="text-body-strong text-foreground">{department ?? "-"}</dd>
        <dt className="text-muted-foreground">직위</dt>
        <dd className="text-body-strong text-foreground">{position ?? "-"}</dd>
        <dt className="text-muted-foreground">고용 형태</dt>
        <dd className="text-body-strong text-foreground">
          {EMPLOYMENT_TYPE_LABELS[registration.employment_type] ?? registration.employment_type}
        </dd>
      </dl>
      <section aria-labelledby="assigned-label" className="flex flex-col gap-2">
        <span id="assigned-label" className="text-label text-foreground">
          담당 과정·기수
        </span>
        {registration.assignments.length ? (
          <ul className="flex flex-col gap-2">
            {registration.assignments.map((a) => {
              const value = toTargetValue(a);
              return (
                <li
                  key={`${a.role}-${value}`}
                  className="flex items-center gap-2 rounded-lg border border-border px-3 py-2"
                >
                  <Badge variant={a.role === "MANAGER" ? "primary" : "secondary"}>{STAFF_ROLE_LABELS[a.role]}</Badge>
                  <span className="text-body-sm text-foreground">{targets.get(value) ?? "-"}</span>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-body-sm text-muted-foreground">담당 없이 신청했어요.</p>
        )}
      </section>
      {rejected ? (
        <Button className="w-full" onClick={onEdit}>
          고쳐서 다시 신청
        </Button>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline" onClick={onEdit}>
            <Pencil />
            신청 내용 수정
          </Button>
          <Button onClick={refresh} disabled={refreshing}>
            <RotateCw />
            새로고침
          </Button>
        </div>
      )}
    </>
  );
}
