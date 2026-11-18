import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { LogOut, Pencil, RotateCw } from "lucide-react";
import { useState } from "react";
import { Controller, useForm, useWatch, type Control } from "react-hook-form";
import { z } from "zod";

import { ApiError } from "@/api/errors";
import { FormField } from "@/components/form-field";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { formatKst } from "@/lib/datetime";

import { logout, meQuery, type Me } from "../api";
import { EMPLOYMENT_TYPE_LABELS, STAFF_ROLE_LABELS } from "../messages";
import { homePath } from "../navigation";
import {
  assignmentLabel,
  bootcampCohorts,
  NO_TEAM,
  scopeOf,
  staffKeys,
  staffOptionsQuery,
  staffRegistrationQuery,
  submitStaffRegistration,
  teamBootcamps,
  teamsOf,
  type StaffOptions,
  type StaffRegistration,
} from "../staff-api";

const MAX_ASSIGNMENTS = 20;

/**
 * 운영진 최초 정보 입력 (Figma `정보 입력`·`승인 대기`·`반려`, decisions A11·A62·A63·F11·F25·F26).
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
  team_id: z.string().min(1, "팀을 골라 주세요."),
  position_id: z.string().min(1, "직위를 골라 주세요."),
  employment_type: z.string().min(1, "고용 형태를 골라 주세요."),
  bootcamp_ids: z.array(z.string()).max(MAX_ASSIGNMENTS, `과정은 ${MAX_ASSIGNMENTS}개까지 고를 수 있어요.`),
  cohort_bootcamp_id: z.string(),
  cohort_id: z.string(),
});
type Values = z.infer<typeof schema>;

function initialValues(options: StaffOptions, initial: StaffRegistration | null): Values {
  const assistant = initial?.assignments.find((a) => a.role === "ASSISTANT" && a.cohort_id);
  const cohort = assistant ? options.cohorts.find((c) => c.id === assistant.cohort_id) : undefined;
  return {
    department_id: initial?.department_id ?? "",
    team_id: initial ? (initial.team_id ?? NO_TEAM) : "",
    position_id: initial?.position_id ?? "",
    employment_type: initial?.employment_type ?? "",
    bootcamp_ids: (initial?.assignments ?? [])
      .filter((a) => a.role === "MANAGER" && a.bootcamp_id)
      .map((a) => a.bootcamp_id as string),
    cohort_bootcamp_id: cohort?.bootcamp_id ?? "",
    cohort_id: cohort?.id ?? "",
  };
}

/**
 * 부서 → 팀 → 직위·고용 형태 → 담당 순서로 앞 칸을 고르면 다음 칸이 나타난다.
 * 앞 칸을 바꾸면 뒤 칸 값은 비운다. 담당은 직위 담당 방식이 있고 팀이 있을 때만 고른다 (A62·A63·F26).
 */
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
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: initialValues(options, initial) });
  const { errors, isSubmitting } = form.formState;
  const [departmentId, teamId, positionId, cohortBootcampId] = useWatch({
    control: form.control,
    name: ["department_id", "team_id", "position_id", "cohort_bootcamp_id"],
  });
  const scope = positionId ? scopeOf(options, positionId) : null;
  const bootcamps = teamBootcamps(options, teamId);
  const showAssignments = scope !== null && teamId !== "" && teamId !== NO_TEAM;

  const clearAssignments = () => {
    form.setValue("bootcamp_ids", []);
    form.setValue("cohort_bootcamp_id", "");
    form.setValue("cohort_id", "");
  };

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    const valueScope = scopeOf(options, values.position_id);
    const withTeam = values.team_id !== NO_TEAM;
    try {
      const saved = await submitStaffRegistration({
        department_id: values.department_id,
        team_id: withTeam ? values.team_id : null,
        position_id: values.position_id,
        employment_type: values.employment_type as StaffRegistration["employment_type"],
        assignments: !withTeam
          ? []
          : valueScope === "COURSE"
            ? values.bootcamp_ids.map((id) => ({ role: "MANAGER" as const, bootcamp_id: id, cohort_id: null }))
            : valueScope === "COHORT" && values.cohort_id
              ? [{ role: "ASSISTANT" as const, bootcamp_id: null, cohort_id: values.cohort_id }]
              : [],
      });
      queryClient.setQueryData(staffKeys.mine, saved);
      onSubmitted();
    } catch (err) {
      if (err instanceof ApiError) {
        for (const [field, message] of Object.entries(err.fieldErrors)) {
          if (field in schema.shape) form.setError(field as keyof Values, { message });
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
            placeholder="부서를 선택하세요"
            error={errors.department_id?.message}
            items={[...options.departments]
              .sort((a, b) => a.name.localeCompare(b.name, "ko"))
              .map((d) => ({ value: d.id, label: d.name }))}
            onChange={() => {
              form.setValue("team_id", "");
              form.setValue("position_id", "");
              form.setValue("employment_type", "");
              clearAssignments();
            }}
          />
          {departmentId ? (
            <SelectField
              control={form.control}
              name="team_id"
              label="팀"
              placeholder="팀을 선택하세요"
              error={errors.team_id?.message}
              items={[
                ...teamsOf(options, departmentId).map((t) => ({ value: t.id, label: t.name })),
                { value: NO_TEAM, label: "선택 안 함 (부서 직속)" },
              ]}
              onChange={clearAssignments}
            />
          ) : null}
          {departmentId && teamId ? (
            <>
              <SelectField
                control={form.control}
                name="position_id"
                label="직위"
                placeholder="직위를 선택하세요"
                error={errors.position_id?.message}
                items={options.positions.map((p) => ({ value: p.id, label: p.name }))}
                onChange={clearAssignments}
              />
              <SelectField
                control={form.control}
                name="employment_type"
                label="고용 형태"
                placeholder="고용 형태를 선택하세요"
                error={errors.employment_type?.message}
                items={options.employment_types.map((t) => ({ value: t, label: EMPLOYMENT_TYPE_LABELS[t] ?? t }))}
              />
            </>
          ) : null}
        </div>

        {showAssignments && scope === "COURSE" ? (
          <CoursePicker control={form.control} bootcamps={bootcamps} error={errors.bootcamp_ids?.message} />
        ) : null}
        {showAssignments && scope === "COHORT" ? (
          <section aria-labelledby="cohort-label" className="flex flex-col gap-2">
            <span id="cohort-label" className="text-label text-foreground">
              담당 기수
            </span>
            <p className="text-caption text-muted-foreground">
              소속 팀 과정을 고른 뒤 기수를 하나 고르면 조교로 등록돼요. 아직 정해지지 않았으면 비워 두세요.
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <SelectField
                control={form.control}
                name="cohort_bootcamp_id"
                label="과정"
                placeholder="과정을 선택하세요"
                error={undefined}
                items={bootcamps.map((b) => ({ value: b.id, label: b.name }))}
                onChange={() => form.setValue("cohort_id", "")}
              />
              {cohortBootcampId ? (
                <CohortField control={form.control} cohorts={bootcampCohorts(options, cohortBootcampId)} />
              ) : null}
            </div>
          </section>
        ) : null}

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
  placeholder,
  items,
  error,
  onChange,
}: {
  control: Control<Values>;
  name: "department_id" | "team_id" | "position_id" | "employment_type" | "cohort_bootcamp_id";
  label: string;
  placeholder: string;
  items: { value: string; label: string }[];
  error: string | undefined;
  onChange?: () => void;
}) {
  return (
    <FormField label={label} error={error}>
      {(field) => (
        <Controller
          control={control}
          name={name}
          render={({ field: selected }) => (
            <Select
              value={selected.value}
              onValueChange={(value) => {
                if (value === selected.value) return;
                selected.onChange(value);
                onChange?.();
              }}
            >
              <SelectTrigger {...field}>
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
      )}
    </FormField>
  );
}

/** COURSE 직위: 소속 팀 과정을 여러 개 체크한다. 운영 매니저로 등록된다 (A62) */
function CoursePicker({
  control,
  bootcamps,
  error,
}: {
  control: Control<Values>;
  bootcamps: StaffOptions["bootcamps"];
  error: string | undefined;
}) {
  return (
    <Controller
      control={control}
      name="bootcamp_ids"
      render={({ field }) => (
        <section aria-labelledby="course-label" className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span id="course-label" className="text-label text-foreground">
              담당 과정
            </span>
            {bootcamps.length ? (
              <span className="text-caption text-muted-foreground">
                {field.value.length} / {bootcamps.length}
              </span>
            ) : null}
          </div>
          <p className="text-caption text-muted-foreground">
            {bootcamps.length
              ? "소속 팀이 담당하는 과정이에요. 고른 과정의 운영 매니저로 등록돼요."
              : "소속 팀이 담당하는 과정이 아직 없어요. 담당 없이 신청할 수 있어요."}
          </p>
          {bootcamps.length ? (
            <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card">
              {bootcamps.map((b) => (
                <li key={b.id} className="flex px-3 py-2.5">
                  <Checkbox
                    checked={field.value.includes(b.id)}
                    onCheckedChange={(checked) =>
                      field.onChange(
                        checked === true ? [...field.value, b.id] : field.value.filter((id) => id !== b.id),
                      )
                    }
                  >
                    {b.name}
                  </Checkbox>
                </li>
              ))}
            </ul>
          ) : null}
          {error ? <p className="text-caption text-destructive-text">{error}</p> : null}
        </section>
      )}
    />
  );
}

/** COHORT 직위: 고른 과정의 기수를 하나 고른다. 승인된 조교가 없는 기수만 보인다 (A63) */
function CohortField({ control, cohorts }: { control: Control<Values>; cohorts: StaffOptions["cohorts"] }) {
  return (
    <FormField label="기수" helper={cohorts.length ? undefined : "조교를 고를 수 있는 기수가 없어요."}>
      {(field) => (
        <Controller
          control={control}
          name="cohort_id"
          render={({ field: selected }) => (
            <Select value={selected.value} onValueChange={selected.onChange} disabled={!cohorts.length}>
              <SelectTrigger {...field}>
                <SelectValue placeholder="기수를 선택하세요" />
              </SelectTrigger>
              <SelectContent>
                {cohorts.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.cohort_number}기
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
  const department = options.departments.find((d) => d.id === registration.department_id)?.name;
  const team = registration.team_id
    ? options.teams.find((t) => t.id === registration.team_id)?.name
    : "선택 안 함 (부서 직속)";
  const position = options.positions.find((p) => p.id === registration.position_id)?.name;
  const roles = new Set(registration.assignments.map((a) => a.role));
  const assignedTitle = roles.size === 1 ? (roles.has("ASSISTANT") ? "담당 기수" : "담당 과정") : "담당 과정·기수";
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
        <dt className="text-muted-foreground">팀</dt>
        <dd className="text-body-strong text-foreground">{team ?? "-"}</dd>
        <dt className="text-muted-foreground">직위</dt>
        <dd className="text-body-strong text-foreground">{position ?? "-"}</dd>
        <dt className="text-muted-foreground">고용 형태</dt>
        <dd className="text-body-strong text-foreground">
          {EMPLOYMENT_TYPE_LABELS[registration.employment_type] ?? registration.employment_type}
        </dd>
      </dl>
      <section aria-labelledby="assigned-label" className="flex flex-col gap-2">
        <span id="assigned-label" className="text-label text-foreground">
          {assignedTitle}
        </span>
        {registration.assignments.length ? (
          <ul className="flex flex-col gap-2">
            {registration.assignments.map((a) => (
              <li
                key={`${a.role}-${a.bootcamp_id ?? ""}-${a.cohort_id ?? ""}`}
                className="flex items-center gap-2 rounded-lg border border-border px-3 py-2"
              >
                <Badge variant="primary">{STAFF_ROLE_LABELS[a.role]}</Badge>
                <span className="text-body-sm text-foreground">{assignmentLabel(options, a) ?? "-"}</span>
              </li>
            ))}
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
