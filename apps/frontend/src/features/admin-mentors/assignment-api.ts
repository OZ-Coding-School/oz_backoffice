import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { ApiError } from "@/api/errors";

import { mentorKeys } from "./api";

export type AssignmentCreate = components["schemas"]["AssignmentCreate"];
export type AssignmentUpdate = components["schemas"]["AssignmentUpdate"];
export type SettlementPolicy = components["schemas"]["MentoringSettlementPolicy"];
export type PayUnit = AssignmentCreate["pay_unit"];

/** 배정이 바뀌면 그 멘토의 배정·단건(활성 배정 기수)·목록을 다시 읽는다 */
function useRefresh(mentorId: string) {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: mentorKeys.assignments(mentorId) });
    void client.invalidateQueries({ queryKey: mentorKeys.detail(mentorId) });
    void client.invalidateQueries({ queryKey: ["admin-mentors", "list"] });
  };
}

/** 기수 배정 추가 (A35): 활성 멘토만, 시작일은 기수 기간 안 */
export function useCreateAssignment(mentorId: string) {
  const refresh = useRefresh(mentorId);
  return useMutation({
    mutationFn: ({ cohortId, body }: { cohortId: string; body: AssignmentCreate }) =>
      unwrap(
        api.POST("/api/v1/admin/cohorts/{cohort_id}/mentor-assignments", {
          params: { path: { cohort_id: cohortId } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
}

/** 기간·정산 조건 수정 (멘토·기수는 못 바꾼다). 종료일 null은 비우기 */
export function useUpdateAssignment(mentorId: string, cohortId: string, assignmentId: string) {
  const refresh = useRefresh(mentorId);
  return useMutation({
    mutationFn: (body: AssignmentUpdate) =>
      unwrap(
        api.PATCH("/api/v1/admin/cohorts/{cohort_id}/mentor-assignments/{assignment_id}", {
          params: { path: { cohort_id: cohortId, assignment_id: assignmentId } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
}

/** 배정 종료(= 비활성화, 그 기수의 대기 신청은 자동 취소)·다시 켜기. 취소된 대기 신청 수를 돌려준다 */
export function useAssignmentActive(mentorId: string, cohortId: string, assignmentId: string) {
  const refresh = useRefresh(mentorId);
  const path = { params: { path: { cohort_id: cohortId, assignment_id: assignmentId } } };
  return useMutation({
    mutationFn: async (active: boolean): Promise<number> => {
      if (active) {
        await unwrap(api.POST("/api/v1/admin/cohorts/{cohort_id}/mentor-assignments/{assignment_id}/reactivate", path));
        return 0;
      }
      const res = await unwrap(
        api.DELETE("/api/v1/admin/cohorts/{cohort_id}/mentor-assignments/{assignment_id}", path),
      );
      return res.canceled_pending_requests;
    },
    onSuccess: refresh,
  });
}

const ERRORS: Record<string, string> = {
  assignment_already_exists: "이 기수에는 이미 활성 배정이 있어요.",
  assignment_start_outside_cohort: "시작일은 기수 기간 안이어야 해요.",
  invalid_assignment_period: "종료일은 시작일과 같거나 뒤여야 해요.",
  assignment_period_ended: "종료일이 지난 배정은 다시 켤 수 없어요. 종료일을 먼저 고쳐 주세요.",
  invalid_pay_amount: "금액을 확인해 주세요.",
  invalid_pay_unit: "단가 기준을 확인해 주세요.",
  mentor_inactive: "비활성 멘토는 배정할 수 없어요.",
  cohort_not_found: "기수를 찾을 수 없어요.",
};

export function assignmentError(e: unknown): string {
  const code = e instanceof ApiError ? e.code : undefined;
  return (code && ERRORS[code]) ?? "처리하지 못했어요. 잠시 후 다시 시도해 주세요.";
}
