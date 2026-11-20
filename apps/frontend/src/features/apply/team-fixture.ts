import type { StudentTeam } from "./api";

/** 내 팀 응답 (A73 필드 포함) 테스트용 */
export function makeStudentTeam(overrides: Partial<StudentTeam> = {}): StudentTeam {
  return {
    id: "t1",
    cohort_id: "c12",
    team_number: 3,
    label: "3팀",
    created_at: "2026-11-03T01:00:00Z",
    mentor: { mentor_id: "m1", display_name: "이멘토", headline: null, expertise: null, accepting_requests: true },
    members: [],
    stats: {
      completed_sessions: 0,
      completed_minutes: 0,
      upcoming_sessions: 0,
      next_session_at: null,
      pending_requests: 0,
      pending_requester_name: null,
    },
    ...overrides,
  };
}
