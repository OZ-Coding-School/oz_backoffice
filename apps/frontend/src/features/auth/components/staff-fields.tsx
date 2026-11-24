import { useWatch, Controller, type Control, type UseFormReturn } from "react-hook-form";
import { X } from "lucide-react";

import { FormField } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { EMPLOYMENT_TYPE_LABELS } from "../messages";
import { bootcampCohorts, NO_TEAM, scopeOf, teamBootcamps, teamsOf, type StaffOptions } from "../staff-api";
import type { StaffFormValues } from "../staff-form";

/**
 * 부서 → 팀 → 직위·고용 형태 → 담당 순서로 앞 칸을 고르면 다음 칸이 나타난다 (F26).
 * 앞 칸을 바꾸면 뒤 칸 값은 비운다. 담당은 직위 담당 방식이 있고 팀이 있을 때만 고른다 (A62·A63).
 * 운영진 승인(F61)은 `wide`면 다른 팀 과정·조교가 있는 기수까지 고를 수 있다(승인 조정 자유, A62).
 */
export function StaffFields({
  form,
  options,
  wide = false,
  wideCohorts,
  courseHelper,
}: {
  form: UseFormReturn<StaffFormValues>;
  options: StaffOptions;
  wide?: boolean;
  /** 넓게 볼 때 기수 목록 (없으면 신청 선택지의 기수) */
  wideCohorts?: StaffOptions["cohorts"];
  courseHelper?: string;
}) {
  const { errors } = form.formState;
  const [departmentId, teamId, positionId, cohortBootcampId] = useWatch({
    control: form.control,
    name: ["department_id", "team_id", "position_id", "cohort_bootcamp_id"],
  });
  const scope = positionId ? scopeOf(options, positionId) : null;
  const bootcamps = wide
    ? [...options.bootcamps].sort((a, b) => a.name.localeCompare(b.name, "ko"))
    : teamBootcamps(options, teamId);
  const cohortsOf = (bootcampId: string) =>
    wide && wideCohorts
      ? wideCohorts.filter((c) => c.bootcamp_id === bootcampId).sort((a, b) => a.cohort_number - b.cohort_number)
      : bootcampCohorts(options, bootcampId);
  const showAssignments = scope !== null && teamId !== "" && (wide || teamId !== NO_TEAM);

  const clearAssignments = () => {
    form.setValue("bootcamp_ids", [], { shouldDirty: true });
    form.setValue("cohort_bootcamp_id", "", { shouldDirty: true });
    form.setValue("cohort_id", "", { shouldDirty: true });
  };

  return (
    <>
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
        <CoursePicker
          control={form.control}
          bootcamps={bootcamps}
          error={errors.bootcamp_ids?.message}
          {...(courseHelper ? { helper: courseHelper } : {})}
        />
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
            {cohortBootcampId ? <CohortField control={form.control} cohorts={cohortsOf(cohortBootcampId)} /> : null}
          </div>
        </section>
      ) : null}
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
  control: Control<StaffFormValues>;
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

/**
 * COURSE 직위: 소속 팀 과정을 드롭다운에서 골라 아래 목록에 추가한다(운영 매니저, A62·F26).
 * 이미 추가한 과정은 드롭다운에서 빠지고, 목록의 X로 뺀다.
 */
function CoursePicker({
  control,
  bootcamps,
  error,
  helper,
}: {
  control: Control<StaffFormValues>;
  bootcamps: StaffOptions["bootcamps"];
  error: string | undefined;
  helper?: string;
}) {
  return (
    <Controller
      control={control}
      name="bootcamp_ids"
      render={({ field }) => {
        const chosen = field.value
          .map((id) => bootcamps.find((b) => b.id === id))
          .filter((b): b is StaffOptions["bootcamps"][number] => b !== undefined);
        const remaining = bootcamps.filter((b) => !field.value.includes(b.id));
        return (
          <section aria-labelledby="course-label" className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span id="course-label" className="text-label text-foreground">
                담당 과정
              </span>
              {bootcamps.length ? (
                <span className="text-caption text-muted-foreground">
                  {chosen.length} / {bootcamps.length}
                </span>
              ) : null}
            </div>
            <p className="text-caption text-muted-foreground">
              {helper ??
                (bootcamps.length
                  ? "소속 팀이 담당하는 과정을 골라 추가하세요. 추가한 과정의 운영 매니저로 등록돼요."
                  : "소속 팀이 담당하는 과정이 아직 없어요. 담당 없이 신청할 수 있어요.")}
            </p>
            {bootcamps.length ? (
              <Select
                value=""
                onValueChange={(id) => field.onChange([...field.value, id])}
                disabled={!remaining.length}
              >
                <SelectTrigger aria-label="담당 과정 추가">
                  <SelectValue placeholder={remaining.length ? "과정을 선택해 추가하세요" : "모든 과정을 추가했어요"} />
                </SelectTrigger>
                <SelectContent>
                  {remaining.map((b) => (
                    <SelectItem key={b.id} value={b.id}>
                      {b.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : null}
            {chosen.length ? (
              <ul
                aria-label="추가한 담당 과정"
                className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card"
              >
                {chosen.map((b) => (
                  <li key={b.id} className="flex items-center gap-2 py-1 pr-1 pl-3">
                    <span className="min-w-0 flex-1 truncate text-body text-foreground">{b.name}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`${b.name} 빼기`}
                      className="px-2"
                      onClick={() => field.onChange(field.value.filter((id) => id !== b.id))}
                    >
                      <X />
                    </Button>
                  </li>
                ))}
              </ul>
            ) : null}
            {error ? <p className="text-caption text-destructive-text">{error}</p> : null}
          </section>
        );
      }}
    />
  );
}

/** COHORT 직위: 고른 과정의 기수를 하나 고른다. 승인된 조교가 없는 기수만 보인다 (A63) */
function CohortField({ control, cohorts }: { control: Control<StaffFormValues>; cohorts: StaffOptions["cohorts"] }) {
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
