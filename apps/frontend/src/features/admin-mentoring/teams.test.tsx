import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffAccess, StaffCohort } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { MentoringSettings } from "./api";
import type { AdminTeam, CohortAssignment } from "./teams-api";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: false });
const COHORT: StaffCohort = {
  id: "c12",
  bootcamp_id: "b1",
  bootcamp_name: "백엔드 부트캠프",
  cohort_number: 12,
  start_date: "2026-09-01",
  end_date: "2027-02-28",
  status: "ONGOING",
};
const SETTINGS: MentoringSettings = {
  cohort_id: "c12",
  allow_1_on_1: true,
  allow_team_mentoring: true,
  allowed_duration: 60,
  default_1on1_minutes: 240,
  default_team_minutes: 360,
  max_pending_requests: 3,
  min_lead_hours: 24,
  weekday_hours: { start: "10:00", end: "22:00" },
  weekend_hours: null,
  updated_at: "2026-11-02T05:10:00Z",
};
const MENTOR = { mentor_id: "m1", name: "김멘토", display_name: "멘토K" };
const member = (id: string, name: string) => ({
  student_id: id,
  name,
  is_signed_up: true,
  status: "ENROLLED" as const,
});
const TEAMS: AdminTeam[] = [
  {
    id: "t1",
    cohort_id: "c12",
    team_number: 1,
    name: "알파",
    label: "알파",
    mentor: MENTOR,
    members: [member("s1", "가수강"), member("s2", "나수강")],
    account: {
      id: "a1",
      valid_from: "2026-09-01",
      valid_until: "2027-02-28",
      is_expired: false,
      total_minutes: 360,
      held_minutes: 60,
      used_minutes: 120,
      remaining_minutes: 180,
    },
    pending_request_count: 1,
    upcoming_session_count: 2,
    completed_session_count: 3,
  },
  {
    id: "t2",
    cohort_id: "c12",
    team_number: 2,
    name: null,
    label: "2팀",
    mentor: MENTOR,
    members: [member("s3", "다수강")],
    account: null,
    pending_request_count: 0,
    upcoming_session_count: 0,
    completed_session_count: 0,
  },
];
const ASSIGNMENT: CohortAssignment = {
  id: "as1",
  cohort_id: "c12",
  mentor_id: "m1",
  mentor_name: "김멘토",
  mentor_display_name: "멘토K",
  start_date: "2026-09-01",
  end_date: null,
  is_active: true,
  deactivated_at: null,
  deactivation_reason: null,
  contract_id: "k1",
  contract: null,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

function access(codes = ["mentoring.team.read", "mentoring.team.manage", "mentoring.balance.manage"]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: [COHORT],
  };
}

function mockApi(opts: { access?: StaffAccess; settings?: MentoringSettings; teams?: AdminTeam[] } = {}) {
  const calls: { path: string; body: unknown; key?: string | null }[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(opts.access ?? access())),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentoring-settings"), () =>
      HttpResponse.json(opts.settings ?? SETTINGS),
    ),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentoring-teams"), () => HttpResponse.json(opts.teams ?? TEAMS)),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentoring-teams/unassigned-students"), () =>
      HttpResponse.json([member("s4", "라수강"), { ...member("s5", "마수강"), is_signed_up: false }]),
    ),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentor-assignments"), () => HttpResponse.json([ASSIGNMENT])),
    http.post(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentoring-teams"), async ({ request }) => {
      const body = await request.json();
      calls.push({ path: "create", body });
      return HttpResponse.json({ ...TEAMS[1], id: "t3", team_number: 3, label: "3팀" }, { status: 201 });
    }),
    http.post(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentoring-balances/grants"), async ({ request }) => {
      const body = await request.json();
      calls.push({ path: "grant", body, key: request.headers.get("Idempotency-Key") });
      return HttpResponse.json({
        granted: [{ owner_id: "t2", account_id: "a2", minutes: 360, created: true }],
        skipped: [{ owner_id: "t1", code: "balance_account_expired", message: "사용 기간이 끝난 계좌예요" }],
      });
    }),
  );
  return calls;
}

beforeEach(() => {
  resetAuth();
  mockSignedIn(ADMIN);
  try {
    localStorage.clear();
  } catch {
    // 저장소가 없어도 이어 간다
  }
});

describe("멘토링 > 팀 관리 (FE-19b)", () => {
  it("메뉴 주소는 현재 기수로 보내고, 팀마다 계좌 잔여·대기 신청·세션 수를 보여 준다", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/mentoring/teams");
    await waitFor(() => expect(router.state.location.pathname).toBe("/admin/cohorts/c12/mentoring/teams"));
    expect(await screen.findByRole("heading", { level: 1, name: "팀 관리" })).toBeInTheDocument();
    expect(screen.getByText("팀 2개 · 팀원 3명")).toBeInTheDocument();
    const alpha = await screen.findByRole("row", { name: "알파" });
    expect(within(alpha).getByText("3시간")).toBeInTheDocument();
    expect(within(alpha).getByText("1건")).toBeInTheDocument();
    expect(within(alpha).getByText("2 · 3")).toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: "2팀" })).getByText("지급 전")).toBeInTheDocument();
    expect(await screen.findByText("팀이 없는 수강 중 수강생 2명")).toBeInTheDocument();
  });

  it("팀 만들기 패널: 담당 멘토와 팀원을 골라 만든다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/cohorts/c12/mentoring/teams");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "팀 만들기" }));
    const panel = await screen.findByRole("dialog", { name: "팀 만들기" });
    await user.click(within(panel).getByRole("button", { name: "만들기" }));
    expect(await within(panel).findByText("담당 멘토를 골라 주세요.")).toBeInTheDocument();
    await user.click(within(panel).getByRole("combobox", { name: "담당 멘토" }));
    await user.click(await screen.findByRole("option", { name: "멘토K (김멘토)" }));
    await user.click(within(panel).getByRole("checkbox", { name: "라수강" }));
    await user.type(within(panel).getByLabelText("이름"), "베타");
    await user.click(within(panel).getByRole("button", { name: "만들기" }));
    await waitFor(() =>
      expect(calls).toContainEqual({ path: "create", body: { name: "베타", mentor_id: "m1", student_ids: ["s4"] } }),
    );
    expect(await screen.findByText("3팀을 만들었어요")).toBeInTheDocument();
  });

  it("팀을 골라 떠오르는 막대에서 시간을 지급하고, 건너뛴 팀은 사유로 보여 준다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/cohorts/c12/mentoring/teams");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("checkbox", { name: "알파 고르기" }));
    await user.click(screen.getByRole("checkbox", { name: "2팀 고르기" }));
    expect(screen.getByText("2팀 선택")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "시간 지급" }));
    const panel = await screen.findByRole("dialog", { name: "팀 시간 지급" });
    await user.click(within(panel).getByRole("button", { name: "지급" }));
    expect(await within(panel).findByText("지급 사유를 적어 주세요.")).toBeInTheDocument();
    await user.type(within(panel).getByLabelText("사유"), "프로젝트 기간");
    await user.click(within(panel).getByRole("button", { name: "지급" }));
    await waitFor(() => expect(calls.find((c) => c.path === "grant")).toBeTruthy());
    const grant = calls.find((c) => c.path === "grant");
    expect(grant?.body).toEqual({
      target: "TEAMS",
      ids: ["t1", "t2"],
      minutes: null,
      valid_from: null,
      valid_until: null,
      reason: "프로젝트 기간",
    });
    expect(grant?.key).toBeTruthy();
    const skipped = await within(panel).findByRole("list", { name: "건너뛴 팀" });
    expect(within(skipped).getByText("알파")).toBeInTheDocument();
    expect(within(skipped).getByText("사용 기간이 끝난 계좌예요")).toBeInTheDocument();
  });

  it("팀 멘토링을 받지 않는 기수는 안내만, 관리 권한이 없으면 버튼·체크가 없다", async () => {
    mockApi({ settings: { ...SETTINGS, allow_team_mentoring: false }, teams: [] });
    await renderRoute("/admin/cohorts/c12/mentoring/teams");
    expect(await screen.findByText("이 기수는 팀 멘토링을 받지 않아요")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "팀 만들기" })).not.toBeInTheDocument();
  });

  it("조회 권한만 있으면 만들기·지급이 없다", async () => {
    mockApi({ access: access(["mentoring.team.read"]) });
    await renderRoute("/admin/cohorts/c12/mentoring/teams");
    expect(await screen.findByRole("row", { name: "알파" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "팀 만들기" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "전체 팀 지급" })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "알파 고르기" })).not.toBeInTheDocument();
  });
});
