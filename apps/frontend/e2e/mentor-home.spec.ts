import { expect, test } from "@playwright/test";

const MENTOR = {
  id: "u9",
  email: "mentor@gmail.com",
  name: "김멘토",
  account_type: "MENTOR",
  phone_number: "01012345678",
  approval_status: "APPROVED",
  approved_at: "2026-11-01T01:00:00Z",
  roles: [{ role: "MENTOR", scope_type: "GLOBAL", scope_id: null, expires_at: null }],
};
const SESSION = {
  id: "s1",
  status: "SCHEDULED",
  title: "멘토K 멘토링 3회차",
  topic: "포트폴리오 리뷰",
  detail: "",
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
  requested_at: null,
  google_meet_url: "https://meet.google.com/abc-defg-hij",
  summary: null,
  record_duration_minutes: null,
  recorded_at: null,
  created_at: null,
  cohort_id: "c12",
  bootcamp_name: "초격차 백엔드",
  cohort_number: 12,
};
const MISSING = {
  ...SESSION,
  id: "s9",
  topic: "ORM 최적화",
  starts_at: "2026-11-13T06:00:00Z",
  ends_at: "2026-11-13T07:00:00Z",
};
const VIEW_COUNTS = { upcoming: 1, record_missing: 1, past: 0, all: 2 };
const COUNTS = { SCHEDULED: 2, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 };

test.describe("멘토 홈", () => {
  // 시각 표시는 단위 테스트가 시간대별로 확인한다
  test.use({ timezoneId: "Asia/Seoul" });

  test("데스크톱: 요약·오늘 세션 Meet 입장·미제출 경고 → 기록 작성 (F57)", async ({ page }) => {
    await page.clock.setFixedTime(new Date("2026-11-20T03:00:00Z"));
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.route("**/api/v1/auth/refresh", (route) =>
      route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
    );
    await page.route("**/api/v1/me", (route) => route.fulfill({ json: MENTOR }));
    await page.route("**/api/v1/me/mentoring/chat/threads**", (route) =>
      route.fulfill({ json: { items: [], total: 0, limit: 50, offset: 0 } }),
    );
    await page.route("**/api/v1/me/mentoring/chat/stream", (route) =>
      route.fulfill({ headers: { "Content-Type": "text/event-stream" }, body: "event: ready\ndata: {}\n\n" }),
    );
    await page.route("**/api/v1/me/mentor-requests**", (route) =>
      route.fulfill({
        json: {
          items: [],
          total: 0,
          limit: 3,
          offset: 0,
          counts: { PENDING: 0, APPROVED: 0, REJECTED: 0, CANCELED: 0 },
        },
      }),
    );
    await page.route("**/api/v1/me/mentor-schedule", (route) =>
      route.fulfill({ json: { mentor_id: "m1", accepting_requests: true, unavailable_periods: [] } }),
    );
    await page.route("**/api/v1/me/mentor-sessions**", (route) => {
      const view = new URL(route.request().url()).searchParams.get("view");
      const items = view === "record_missing" ? [MISSING] : [SESSION];
      return route.fulfill({
        json: { items, total: items.length, limit: 3, offset: 0, counts: COUNTS, view_counts: VIEW_COUNTS },
      });
    });
    await page.route("**/api/v1/mentoring/sessions/s9**", (route) =>
      route.fulfill({
        json: route.request().url().endsWith("/note") ? { session_id: "s9", body: null, updated_at: null } : MISSING,
      }),
    );

    await page.goto("/");
    const summary = page.getByRole("list", { name: "할 일 요약" });
    await expect(summary.getByRole("link", { name: /오늘 세션/ })).toContainText("1회");
    await expect(
      page.getByRole("region", { name: "오늘·다가오는 세션" }).getByRole("link", { name: "Meet 입장" }),
    ).toBeVisible();
    await page.getByRole("link", { name: "기록 작성" }).click();
    await expect(page).toHaveURL(/\/mentor\/sessions\/s9$/);
  });
});
