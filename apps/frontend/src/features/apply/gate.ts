import { useQuery } from "@tanstack/react-query";

import type { components } from "@/api/schema.gen";
import { activeCohort, enrollmentsQuery, type ActiveCohort } from "@/features/member/api";
import { balancesQuery, mentoringSettingsQuery, type BalanceAccount } from "@/features/requests/api";

import { mentorQuery, myTeamsQuery, type MentorProfile, type StudentTeam } from "./api";

export type MentoringSettings = components["schemas"]["MentoringSettingsSummary"];
export type ApplyKind = "one" | "team";

export type BlockReason =
  | "no_enrollment"
  | "read_only"
  | "not_allowed"
  | "one_on_one_not_allowed"
  | "team_not_allowed"
  | "no_team"
  | "no_time"
  | "team_no_time"
  | "mentor_not_accepting";

export const BLOCK_MESSAGES: Record<BlockReason, { title: string; description: string }> = {
  no_enrollment: { title: "수강 등록이 없어요", description: "수강 중인 기수가 있어야 멘토링을 신청할 수 있어요." },
  read_only: {
    title: "수강이 끝나 새 신청을 할 수 없어요",
    description: "지난 신청과 진행 기록은 신청 내역에서 볼 수 있어요.",
  },
  not_allowed: { title: "이 기수는 멘토링 신청을 받지 않아요", description: "운영진에게 문의해 주세요." },
  one_on_one_not_allowed: { title: "이 기수는 1:1 멘토링을 받지 않아요", description: "운영진에게 문의해 주세요." },
  team_not_allowed: { title: "이 기수는 팀 멘토링을 받지 않아요", description: "운영진에게 문의해 주세요." },
  no_team: { title: "아직 속한 팀이 없어요", description: "운영진이 팀을 만들면 팀 멘토링을 신청할 수 있어요." },
  no_time: {
    title: "남은 1:1 시간이 없어요",
    description: "운영진이 시간을 지급하면 신청할 수 있어요. 보낸 신청은 신청 내역에서 볼 수 있어요.",
  },
  team_no_time: {
    title: "팀 계좌에 남은 시간이 없어요",
    description: "운영진이 팀에 시간을 지급하면 신청할 수 있어요. 보낸 신청은 신청 내역에서 볼 수 있어요.",
  },
  mentor_not_accepting: {
    title: "담당 멘토가 지금은 신청을 받지 않아요",
    description: "멘토가 신청 받기를 켜면 신청할 수 있어요.",
  },
};

/** 기수가 허용하는 종류 (F30·F31) */
export function allowedKinds(settings: MentoringSettings | undefined): ApplyKind[] {
  if (!settings) return [];
  return [
    ...(settings.allow_team_mentoring ? (["team"] as const) : []),
    ...(settings.allow_1_on_1 ? (["one"] as const) : []),
  ];
}

export function accountOf(
  accounts: readonly BalanceAccount[],
  owner: { type: "STUDENT" | "TEAM"; id: string },
): BalanceAccount | undefined {
  return accounts.find((a) => a.owner_type === owner.type && a.owner_id === owner.id);
}

/** 계좌가 없거나 사용 기간이 끝났거나 남은 시간이 진행 단위보다 적으면 신청할 수 없다 (F30) */
function outOfTime(account: BalanceAccount | undefined, unit: number): boolean {
  return !account || account.is_expired || account.remaining_minutes < unit;
}

export function blockReason({
  cohort,
  settings,
  kind,
  account,
  team,
  teamMentor,
}: {
  cohort: ActiveCohort | null;
  settings: MentoringSettings | undefined;
  kind: ApplyKind | null;
  account: BalanceAccount | undefined;
  team?: StudentTeam | undefined;
  teamMentor?: Pick<MentorProfile, "accepting_requests"> | undefined;
}): BlockReason | null {
  if (!cohort) return "no_enrollment";
  if (cohort.readOnly) return "read_only";
  if (!settings) return null;
  if (allowedKinds(settings).length === 0) return "not_allowed";
  if (kind === "one") {
    if (!settings.allow_1_on_1) return "one_on_one_not_allowed";
    if (outOfTime(account, settings.allowed_duration)) return "no_time";
  }
  if (kind === "team") {
    if (!settings.allow_team_mentoring) return "team_not_allowed";
    if (!team) return "no_team";
    if (outOfTime(account, settings.allowed_duration)) return "team_no_time";
    if (teamMentor && !teamMentor.accepting_requests) return "mentor_not_accepting";
  }
  return null;
}

export interface ApplyGate {
  loading: boolean;
  error: boolean;
  cohort: ActiveCohort | null;
  settings: MentoringSettings | undefined;
  kinds: ApplyKind[];
  team: StudentTeam | undefined;
  teamMentor: MentorProfile | undefined;
  oneAccount: BalanceAccount | undefined;
  teamAccount: BalanceAccount | undefined;
  blocked: (kind: ApplyKind | null) => BlockReason | null;
}

/** 신청 첫머리 판정 (F28·F30·F31). 대기 신청 최대 건수는 서버 오류로만 알린다 */
export function useApplyGate(): ApplyGate {
  const enrollments = useQuery(enrollmentsQuery);
  const cohort = enrollments.data ? activeCohort(enrollments.data) : null;
  const enrolled = !!cohort && !cohort.readOnly;
  const cohortId = cohort?.enrollment.cohort_id ?? "";
  const settings = useQuery({ ...mentoringSettingsQuery(cohortId), enabled: enrolled });
  const balances = useQuery({ ...balancesQuery, enabled: enrolled });
  const teams = useQuery({ ...myTeamsQuery, enabled: enrolled && !!settings.data?.allow_team_mentoring });
  const team = teams.data?.as_student.find((t) => t.cohort_id === cohortId);
  const teamMentor = useQuery({ ...mentorQuery(cohortId, team?.mentor.mentor_id ?? ""), enabled: !!team });
  const oneAccount =
    cohort && balances.data
      ? accountOf(balances.data, { type: "STUDENT", id: cohort.enrollment.student_id })
      : undefined;
  const teamAccount = team && balances.data ? accountOf(balances.data, { type: "TEAM", id: team.id }) : undefined;
  const loading =
    enrollments.isPending ||
    (enrolled &&
      (settings.isPending ||
        balances.isPending ||
        (!!settings.data?.allow_team_mentoring && teams.isPending) ||
        (!!team && teamMentor.isPending)));
  return {
    loading,
    error: enrollments.isError || settings.isError || balances.isError || teams.isError,
    cohort,
    settings: settings.data,
    kinds: allowedKinds(settings.data),
    team,
    teamMentor: teamMentor.data,
    oneAccount,
    teamAccount,
    blocked: (kind) =>
      loading
        ? null
        : blockReason({
            cohort,
            settings: settings.data,
            kind,
            account: kind === "team" ? teamAccount : oneAccount,
            team,
            teamMentor: teamMentor.data,
          }),
  };
}
