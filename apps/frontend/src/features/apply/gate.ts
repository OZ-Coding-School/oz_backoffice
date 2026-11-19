import { useQuery } from "@tanstack/react-query";

import { activeCohort, enrollmentsQuery, type ActiveCohort } from "@/features/member/api";
import { balancesQuery, mentoringSettingsQuery, type BalanceAccount } from "@/features/requests/api";
import type { components } from "@/api/schema.gen";

export type MentoringSettings = components["schemas"]["MentoringSettingsSummary"];

export type BlockReason = "no_enrollment" | "read_only" | "one_on_one_not_allowed" | "no_time";

export const BLOCK_MESSAGES: Record<BlockReason, { title: string; description: string }> = {
  no_enrollment: { title: "수강 등록이 없어요", description: "수강 중인 기수가 있어야 멘토링을 신청할 수 있어요." },
  read_only: {
    title: "수강이 끝나 새 신청을 할 수 없어요",
    description: "지난 신청과 진행 기록은 신청 내역에서 볼 수 있어요.",
  },
  one_on_one_not_allowed: { title: "이 기수는 1:1 멘토링을 받지 않아요", description: "운영진에게 문의해 주세요." },
  no_time: {
    title: "남은 1:1 시간이 없어요",
    description: "운영진이 시간을 지급하면 신청할 수 있어요. 보낸 신청은 신청 내역에서 볼 수 있어요.",
  },
};

export interface ApplyGate {
  loading: boolean;
  error: boolean;
  cohort: ActiveCohort | null;
  settings: MentoringSettings | undefined;
  account: BalanceAccount | undefined;
  blocked: BlockReason | null;
}

/** 1:1 계좌: 사용 기간이 끝났거나 남은 시간이 진행 단위보다 적으면 신청할 수 없다 (F30) */
export function oneOnOneAccount(accounts: readonly BalanceAccount[], studentId: string): BalanceAccount | undefined {
  return accounts.find((a) => a.owner_type === "STUDENT" && a.owner_id === studentId);
}

export function blockReason({
  cohort,
  settings,
  account,
}: {
  cohort: ActiveCohort | null;
  settings: MentoringSettings | undefined;
  account: BalanceAccount | undefined;
}): BlockReason | null {
  if (!cohort) return "no_enrollment";
  if (cohort.readOnly) return "read_only";
  if (settings && !settings.allow_1_on_1) return "one_on_one_not_allowed";
  if (settings && (!account || account.is_expired || account.remaining_minutes < settings.allowed_duration)) {
    return "no_time";
  }
  return null;
}

/** 신청 첫머리 판정 (F28·F30). 대기 신청 최대 건수는 서버 오류로만 알린다 */
export function useApplyGate(): ApplyGate {
  const enrollments = useQuery(enrollmentsQuery);
  const cohort = enrollments.data ? activeCohort(enrollments.data) : null;
  const enrolled = !!cohort && !cohort.readOnly;
  const cohortId = cohort?.enrollment.cohort_id ?? "";
  const settings = useQuery({ ...mentoringSettingsQuery(cohortId), enabled: enrolled });
  const balances = useQuery({ ...balancesQuery, enabled: enrolled });
  const account = cohort && balances.data ? oneOnOneAccount(balances.data, cohort.enrollment.student_id) : undefined;
  const loading = enrollments.isPending || (enrolled && (settings.isPending || balances.isPending));
  return {
    loading,
    error: enrollments.isError || settings.isError || balances.isError,
    cohort,
    settings: settings.data,
    account,
    blocked: loading ? null : blockReason({ cohort, settings: settings.data, account }),
  };
}
