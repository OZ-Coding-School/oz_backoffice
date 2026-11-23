import { expect, test } from "@playwright/test";

test("로그인하지 않고 홈에 오면 로그인 화면이 뜬다", async ({ page }) => {
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ status: 401, json: { error: { code: "refresh_token_missing", message: "" } } }),
  );
  await page.goto("/");
  await expect(page).toHaveTitle("오즈코딩스쿨 운영 행정 지원 플랫폼");
  await expect(page.getByRole("heading", { level: 1, name: "로그인" })).toBeVisible();
  await expect(page).toHaveURL(/\/login\?redirect=%2F$/);
});

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
const SESSION = {
  id: "s1",
  status: "SCHEDULED",
  title: "멘토K 멘토링 3회차",
  topic: "포트폴리오 리뷰",
  detail: "README 질문",
  starts_at: "2026-11-20T05:00:00Z",
  ends_at: "2026-11-20T06:00:00Z",
  request_id: "r1",
  team_id: null,
  team_label: null,
  requester_id: "st12",
  requester_name: "가수강",
  mentor_id: "m1",
  mentor_display_name: "멘토K",
  mentor_headline: null,
  participants: [{ student_id: "st12", name: "가수강" }],
  actual_started_at: null,
  actual_ended_at: null,
  cancel_reason: null,
  canceled_by: null,
  canceled_at: null,
  balance: { state: "HELD", minutes: 60 },
  approved_rank: 1,
  requested_at: "2026-11-14T13:30:00Z",
  google_meet_url: "https://meet.google.com/abc-defg-hij",
  summary: null,
  record_duration_minutes: null,
  recorded_at: null,
  created_at: "2026-11-14T13:40:00Z",
};
const COUNTS = { SCHEDULED: 1, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 };

test("휴대폰: 수강생 홈 요약과 오늘 세션의 Meet 입장, 요약에서 진행 기록 예정 탭으로 (F42)", async ({ page }) => {
  await page.clock.setFixedTime(new Date("2026-11-20T03:00:00Z")); // 11/20 12:00 KST
  await page.setViewportSize({ width: 390, height: 844 });
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
        allow_team_mentoring: false,
        allowed_duration: 30,
        min_lead_hours: 24,
        max_pending_requests: 3,
      },
    }),
  );
  await page.route("**/api/v1/me/balances", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/me/mentoring/chat/threads**", (route) =>
    route.fulfill({ json: { items: [], total: 0, limit: 50, offset: 0 } }),
  );
  await page.route("**/api/v1/me/mentoring/chat/stream", (route) =>
    route.fulfill({ headers: { "Content-Type": "text/event-stream" }, body: "event: ready\ndata: {}\n\n" }),
  );
  await page.route("**/api/v1/me/mentoring/requests**", (route) =>
    route.fulfill({
      json: { items: [], total: 0, limit: 2, offset: 0, counts: { PENDING: 0, APPROVED: 1, REJECTED: 0, CANCELED: 0 } },
    }),
  );
  await page.route("**/api/v1/me/mentoring/sessions**", (route) =>
    route.fulfill({ json: { items: [SESSION], total: 1, limit: 20, offset: 0, counts: COUNTS } }),
  );

  await page.goto("/");
  const summary = page.getByRole("list", { name: "할 일 요약" });
  await expect(summary.getByRole("link", { name: /오늘 멘토링\s*1회/ })).toBeVisible();
  await expect(summary.getByRole("link", { name: /승인 대기 신청\s*0건/ })).toBeVisible();
  const card = page.getByRole("region", { name: "멘토링" });
  await expect(card.getByRole("link", { name: /포트폴리오 리뷰/ })).toContainText("오늘 14:00~15:00");
  await expect(card.getByRole("link", { name: "Meet 입장" })).toHaveAttribute(
    "href",
    "https://meet.google.com/abc-defg-hij",
  );

  await summary.getByRole("link", { name: /오늘 멘토링/ }).click();
  await expect(page).toHaveURL(/\/mentoring\/sessions\?tab=scheduled$/);
});
