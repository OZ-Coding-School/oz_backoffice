import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { LogOut, Pencil, RotateCw } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError } from "@/api/errors";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { formatKst } from "@/lib/datetime";

import { logout, meQuery, type Me } from "../api";
import { EMPLOYMENT_TYPE_LABELS } from "../messages";
import { homePath } from "../navigation";
import {
  assignmentLabel,
  staffKeys,
  staffOptionsQuery,
  staffRegistrationQuery,
  submitStaffRegistration,
  type StaffOptions,
  type StaffRegistration,
} from "../staff-api";
import { staffFormSchema, staffFormValues, staffPayload, type StaffFormValues } from "../staff-form";
import { StaffFields } from "./staff-fields";

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
  const form = useForm<StaffFormValues>({
    resolver: zodResolver(staffFormSchema),
    defaultValues: staffFormValues(options, initial),
  });
  const { isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const saved = await submitStaffRegistration(staffPayload(options, values));
      queryClient.setQueryData(staffKeys.mine, saved);
      onSubmitted();
    } catch (err) {
      if (err instanceof ApiError) {
        for (const [field, message] of Object.entries(err.fieldErrors)) {
          if (field in staffFormSchema.shape) form.setError(field as keyof StaffFormValues, { message });
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
        <StaffFields form={form} options={options} />

        <Button type="submit" disabled={isSubmitting} className="w-full">
          승인 신청
        </Button>
      </form>
    </>
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
  // 담당 방식은 직위가 정한다 (A89): 과정이면 '담당 과정', 기수면 '담당 기수'
  const kinds = new Set(registration.assignments.map((a) => (a.cohort_id ? "cohort" : "course")));
  const assignedTitle = kinds.size === 1 ? (kinds.has("cohort") ? "담당 기수" : "담당 과정") : "담당 과정·기수";
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
                key={`${a.bootcamp_id ?? ""}-${a.cohort_id ?? ""}`}
                className="flex items-center gap-2 rounded-lg border border-border px-3 py-2"
              >
                <Badge variant="primary">{a.cohort_id ? "기수" : "과정"}</Badge>
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
