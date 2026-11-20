import { expect, test, type Page } from "@playwright/test";

const ME = {
  id: "u1",
  email: "student@gmail.com",
  name: "가수강",
  account_type: "STUDENT",
  phone_number: "01012345678",
  approval_status: "APPROVED",
  approved_at: "2026-11-16T01:00:00Z",
  roles: [{ role: "STUDENT", scope_type: "COHORT", scope_id: "c12", expires_at: null }],
};
const ENROLLMENT = {
  student_id: "st12",
  cohort_id: "c12",
  bootcamp_id: "b1",
  bootcamp_name: "초격차 백엔드",
  cohort_number: 12,
  cohort_status: "ONGOING",
  start_date: "2026-10-01",
  end_date: "2027-03-31",
  status: "ENROLLED",
  enrolled_at: "2026-10-01",
  ended_at: null,
};
const ACCOUNTS = [
  {
    id: "a2",
    owner_type: "TEAM",
    owner_id: "t3",
    owner_name: "3팀 알파",
    valid_from: "2026-10-01",
    valid_until: "2027-01-31",
    is_expired: false,
    total_minutes: 480,
    held_minutes: 0,
    used_minutes: 180,
    remaining_minutes: 300,
  },
  {
    id: "a1",
    owner_type: "STUDENT",
    owner_id: "st12",
    owner_name: "가수강",
    valid_from: "2026-10-01",
    valid_until: "2027-01-31",
    is_expired: false,
    total_minutes: 360,
    held_minutes: 60,
    used_minutes: 90,
    remaining_minutes: 210,
  },
];
const tx = (id: string, type: string, amount: number, remaining: number, reason: string, at: string) => ({
  id,
  type,
  amount,
  after_remaining: remaining,
  after_held: 0,
  reason,
  created_at: at,
});

async function mockApi(page: Page) {
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ME }));
  await page.route("**/api/v1/me/enrollments", (route) => route.fulfill({ json: [ENROLLMENT] }));
  await page.route("**/api/v1/me/mentoring/settings**", (route) =>
    route.fulfill({
      json: {
        cohort_id: "c12",
        allow_1_on_1: true,
        allow_team_mentoring: true,
        allowed_duration: 30,
        min_lead_hours: 24,
        max_pending_requests: 3,
      },
    }),
  );
  await page.route("**/api/v1/me/balances", (route) => route.fulfill({ json: ACCOUNTS }));
  await page.route("**/api/v1/me/mentoring-teams", (route) =>
    route.fulfill({
      json: {
        as_student: [
          {
            id: "t3",
            cohort_id: "c12",
            team_number: 3,
            label: "알파",
            created_at: "2026-11-03T01:00:00Z",
            mentor: {
              mentor_id: "m2",
              display_name: "이멘토",
              headline: "스타트업 CTO",
              expertise: "FastAPI",
              accepting_requests: true,
            },
            members: [{ student_id: "st12", name: "가수강", status: "ENROLLED" }],
            stats: {
              completed_sessions: 0,
              completed_minutes: 0,
              upcoming_sessions: 0,
              next_session_at: null,
              pending_requests: 0,
              pending_requester_name: null,
            },
          },
        ],
        as_mentor: [],
      },
    }),
  );
  await page.route("**/api/v1/me/mentoring/sessions**", (route) =>
    route.fulfill({
      json: {
        items: [],
        total: 0,
        limit: 3,
        offset: 0,
        counts: { SCHEDULED: 0, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 },
      },
    }),
  );
  await page.route("**/api/v1/me/balances/a1/transactions**", (route) =>
    route.fulfill({
      json: [
        tx("t2", "HOLD", 60, 210, "멘토링 신청", "2026-11-16T01:02:00Z"),
        tx("t1", "STAFF_GRANT", 240, 270, "기본 지급", "2026-10-31T15:00:00Z"),
      ],
    }),
  );
  await page.route("**/api/v1/me/balances/a2/transactions**", (route) =>
    route.fulfill({ json: [tx("u1", "STAFF_GRANT", 480, 480, "팀 기본 지급", "2026-11-01T00:00:00Z")] }),
  );
}

test("휴대폰: 더보기 → 시간 지급·차감 내역 → 팀 계좌로 바꾸기 (F36·F38)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockApi(page);
  await page.goto("/");
  const tabs = page.getByRole("navigation", { name: "하단 메뉴" });
  await tabs.getByRole("button", { name: "더보기" }).click();
  await page.getByRole("dialog", { name: "더보기" }).getByRole("link", { name: "시간 지급·차감 내역" }).click();
  await expect(page.getByRole("heading", { name: "시간 지급·차감 내역" })).toBeVisible();
  await expect(tabs.getByRole("button", { name: "더보기" })).toHaveAttribute("aria-current", "page");
  const ledger = page.getByRole("region", { name: "내역" });
  await expect(ledger.getByText("멘토링 신청").filter({ visible: true })).toBeVisible();
  await page
    .getByRole("navigation", { name: "계좌" })
    .getByRole("link", { name: /3팀 알파 계좌/ })
    .click();
  await expect(ledger.getByText("팀 기본 지급").filter({ visible: true })).toBeVisible();
});

test("휴대폰: 더보기 → 내 팀 (F39)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("navigation", { name: "하단 메뉴" }).getByRole("button", { name: "더보기" }).click();
  await page.getByRole("dialog", { name: "더보기" }).getByRole("link", { name: "내 팀" }).click();
  const team = page.getByRole("region", { name: "알파" });
  await expect(team.getByText("5시간")).toBeVisible();
  await expect(team.getByText("아직 팀 세션이 없어요")).toBeVisible();
  await expect(page.getByRole("link", { name: "팀 멘토링 신청" })).toHaveAttribute(
    "href",
    "/mentoring/apply?kind=team",
  );
});
