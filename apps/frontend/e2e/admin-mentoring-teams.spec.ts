import { expect, test } from "@playwright/test";

const ADMIN = {
  id: "u0",
  email: "boss@nextrunners.co.kr",
  name: "김관리",
  account_type: "STAFF",
  phone_number: null,
  approval_status: "APPROVED",
  approved_at: "2026-11-01T01:00:00Z",
  is_super_admin: true,
};
const ACCESS = {
  is_super_admin: true,
  position: null,
  permissions: [
    "mentoring.settings.read",
    "mentoring.team.read",
    "mentoring.team.manage",
    "mentoring.balance.manage",
  ].map((code) => ({
    code,
    is_global: true,
    bootcamp_ids: [],
    cohort_ids: [],
  })),
  cohorts: [
    {
      id: "c12",
      bootcamp_id: "b1",
      bootcamp_name: "백엔드 부트캠프",
      cohort_number: 12,
      start_date: "2026-09-01",
      end_date: "2027-02-28",
      status: "ONGOING",
    },
  ],
};

test("멘토링 > 팀 관리: 메뉴로 현재 기수 팀 목록에 들어가 팀을 골라 시간을 지급한다 (FE-19b)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let grant: Record<string, unknown> | null = null;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/admin/cohorts/c12/mentoring-settings", (route) =>
    route.fulfill({
      json: {
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
      },
    }),
  );
  await page.route("**/api/v1/admin/cohorts/c12/mentoring-teams/unassigned-students", (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route("**/api/v1/admin/cohorts/c12/mentoring-teams", (route) =>
    route.fulfill({
      json: [
        {
          id: "t1",
          cohort_id: "c12",
          team_number: 1,
          name: "알파",
          label: "알파",
          mentor: { mentor_id: "m1", name: "김멘토", display_name: "멘토K" },
          members: [{ student_id: "s1", name: "가수강", is_signed_up: true, status: "ENROLLED" }],
          account: null,
          pending_request_count: 0,
          upcoming_session_count: 0,
          completed_session_count: 0,
        },
      ],
    }),
  );
  await page.route("**/api/v1/admin/cohorts/c12/mentoring-balances/grants", async (route) => {
    grant = route.request().postDataJSON() as Record<string, unknown>;
    return route.fulfill({
      json: { granted: [{ owner_id: "t1", account_id: "a1", minutes: 360, created: true }], skipped: [] },
    });
  });

  await page.goto("/admin");
  await page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "멘토링" }).click();
  await page.getByRole("navigation", { name: "메뉴" }).getByRole("link", { name: "팀 관리" }).click();
  await expect(page).toHaveURL(/\/admin\/cohorts\/c12\/mentoring\/teams$/);
  await page.getByRole("checkbox", { name: "알파 고르기" }).click();
  await page.getByRole("button", { name: "시간 지급" }).click();
  const panel = page.getByRole("dialog", { name: "팀 시간 지급" });
  await panel.getByLabel("사유").fill("프로젝트 기간");
  await panel.getByRole("button", { name: "지급" }).click();
  await expect(page.getByText("1팀에 시간을 지급했어요")).toBeVisible();
  expect(grant).toMatchObject({ target: "TEAMS", ids: ["t1"], reason: "프로젝트 기간" });
});
