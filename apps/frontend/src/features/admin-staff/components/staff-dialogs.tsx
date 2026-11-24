import { zodResolver } from "@hookform/resolvers/zod";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { StaffFields } from "@/features/auth/components/staff-fields";
import { STAFF_ROLE_LABELS } from "@/features/auth/messages";
import { NO_TEAM, type StaffOptions } from "@/features/auth/staff-api";
import { staffFormSchema, staffFormValues, type StaffFormValues } from "@/features/auth/staff-form";
import { useDebounced } from "@/lib/use-debounced";
import { cn } from "@/lib/utils";

import {
  assignmentsSummary,
  employeeSearchQuery,
  useAddStaff,
  useRemoveStaff,
  useUpdateEmployee,
  type Employee,
  type StaffMember,
  type StaffRole,
  type StaffTarget,
} from "../api";

function errorText(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.message : fallback;
}

function orgLine(options: StaffOptions, e: Employee): string {
  const department = options.departments.find((d) => d.id === e.department_id)?.name ?? "—";
  const team = e.team_id ? (options.teams.find((t) => t.id === e.team_id)?.name ?? "—") : "부서 직속";
  const position = options.positions.find((p) => p.id === e.position_id)?.name ?? "—";
  return `${department} · ${team} · ${position}`;
}

/** 소속 수정 (org.manage, F62): 부서 → 팀 → 직위·고용 형태. 담당은 담당자 탭에서 바꾼다 */
export function EditEmployeeDialog({
  employee,
  options,
  onClose,
}: {
  employee: Employee;
  options: StaffOptions;
  onClose: () => void;
}) {
  const form = useForm<StaffFormValues>({
    resolver: zodResolver(staffFormSchema),
    defaultValues: staffFormValues(options, { ...employee, assignments: [] }),
  });
  const update = useUpdateEmployee(employee.id);
  const [error, setError] = useState<string | null>(null);
  const name = employee.user?.name ?? "직원";
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await update.mutateAsync({
        department_id: v.department_id,
        team_id: v.team_id === NO_TEAM ? null : v.team_id,
        position_id: v.position_id,
        employment_type: v.employment_type as Employee["employment_type"],
      });
      toast.success(`${name}님의 소속을 바꿨어요`);
      onClose();
    } catch (e) {
      setError(errorText(e, "저장하지 못했어요. 잠시 후 다시 시도해 주세요."));
    }
  });
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-150 flex-col gap-4 p-6">
        <div className="flex flex-col gap-1 pr-8">
          <DialogTitle className="text-h2 text-foreground">소속 수정 · {name}</DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            부서·팀·직위·고용 형태를 바꿔요. 담당 과정·기수는 담당자 탭에서 바꿔요.
          </DialogDescription>
        </div>
        <dl className="grid grid-cols-[auto_1fr_auto] gap-x-6 gap-y-0.5 rounded-lg bg-muted px-4 py-3">
          <dt className="text-caption text-muted-foreground">이름</dt>
          <dt className="text-caption text-muted-foreground">이메일</dt>
          <dt className="text-caption text-muted-foreground">담당</dt>
          <dd className="text-body-strong text-foreground">{name}</dd>
          <dd className="break-all text-body-strong text-foreground">{employee.user?.email ?? "—"}</dd>
          <dd className="text-body-strong text-foreground">{assignmentsSummary(employee.assignments ?? [])}</dd>
        </dl>
        <form aria-label="소속" noValidate onSubmit={(e) => void onSubmit(e)} className="flex flex-col gap-4">
          <StaffFields form={form} options={options} withAssignments={false} />
          {error ? <Alert variant="error" title={error} /> : null}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              취소
            </Button>
            <Button type="submit" disabled={update.isPending}>
              저장
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** 담당자 추가 (staff.assign, F62·A83): 직원을 찾아 하나 고르고 역할을 고른다. 이미 담당 중이면 막는다 */
export function AddStaffDialog({
  target,
  targetName,
  members,
  options,
  onClose,
}: {
  target: StaffTarget;
  targetName: string;
  members: readonly StaffMember[];
  options: StaffOptions;
  onClose: () => void;
}) {
  const [q, setQ] = useState("");
  const query = useDebounced(q.trim());
  const found = useQuery({ ...employeeSearchQuery(query), placeholderData: keepPreviousData });
  const [selected, setSelected] = useState("");
  const [role, setRole] = useState<StaffRole>(target.kind === "cohort" ? "ASSISTANT" : "MANAGER");
  const add = useAddStaff(target);
  const [error, setError] = useState<string | null>(null);
  const taken = new Set(members.map((m) => m.employee_id));
  const employees = found.data ?? [];

  const submit = async () => {
    setError(null);
    try {
      await add.mutateAsync({ employee_id: selected, role });
      toast.success("담당자를 추가했어요");
      onClose();
    } catch (e) {
      setError(errorText(e, "추가하지 못했어요. 잠시 후 다시 시도해 주세요."));
    }
  };

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-150 flex-col gap-4 p-6">
        <div className="flex flex-col gap-1 pr-8">
          <DialogTitle className="text-h2 text-foreground">담당자 추가</DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            {targetName}의 담당자로 추가할 직원과 역할을 고르세요.
          </DialogDescription>
        </div>
        <div className="relative">
          <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            aria-label="직원 검색"
            placeholder="이름 또는 이메일로 찾기"
            value={q}
            maxLength={50}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
          />
        </div>
        {found.isPending ? (
          <div className="flex justify-center py-6">
            <Spinner />
          </div>
        ) : employees.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border py-6 text-center text-body text-muted-foreground">
            찾는 직원이 없어요.
          </p>
        ) : (
          <RadioGroup
            aria-label="추가할 직원"
            value={selected}
            onValueChange={setSelected}
            className="flex max-h-72 flex-col gap-0 overflow-y-auto rounded-lg border border-border"
          >
            {employees.map((e) => {
              const already = taken.has(e.id);
              return (
                <div
                  key={e.id}
                  className={cn(
                    "flex items-center gap-3 border-b border-border px-4 py-3 last:border-b-0",
                    selected === e.id && "bg-accent/50",
                  )}
                >
                  <RadioGroupItem value={e.id} disabled={already} aria-label={e.user?.name ?? "직원"}>
                    {""}
                  </RadioGroupItem>
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="text-body-strong text-foreground">
                      {e.user?.name ?? "—"} · {e.user?.email ?? "—"}
                    </span>
                    <span className="text-caption text-muted-foreground">{orgLine(options, e)}</span>
                  </span>
                  {already ? <Badge variant="success">담당 중</Badge> : null}
                </div>
              );
            })}
          </RadioGroup>
        )}
        <div className="flex flex-col gap-1.5">
          <span id="role-label" className="text-label text-foreground">
            역할
          </span>
          <Select value={role} onValueChange={(v) => setRole(v as StaffRole)}>
            <SelectTrigger aria-labelledby="role-label">
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
        </div>
        {error ? <Alert variant="error" title={error} /> : null}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            취소
          </Button>
          <Button disabled={!selected || add.isPending} onClick={() => void submit()}>
            추가
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** 담당자 해제 확인 */
export function RemoveStaffDialog({
  target,
  targetName,
  member,
  onClose,
}: {
  target: StaffTarget;
  targetName: string;
  member: StaffMember;
  onClose: () => void;
}) {
  const remove = useRemoveStaff(target);
  const [error, setError] = useState<string | null>(null);
  const name = member.user?.name ?? "직원";
  const submit = async () => {
    setError(null);
    try {
      await remove.mutateAsync(member.id);
      toast.success(`${name}님을 담당자에서 뺐어요`);
      onClose();
    } catch (e) {
      setError(errorText(e, "해제하지 못했어요. 잠시 후 다시 시도해 주세요."));
    }
  };
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-110 flex-col gap-4 p-6">
        <DialogTitle className="text-h2 text-foreground">담당자에서 뺄까요?</DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          {name}님을 {targetName} {STAFF_ROLE_LABELS[member.role]}에서 빼요. 그 범위의 권한도 함께 없어져요.
        </DialogDescription>
        {error ? <Alert variant="error" title={error} /> : null}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            돌아가기
          </Button>
          <Button variant="destructive" disabled={remove.isPending} onClick={() => void submit()}>
            빼기
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
