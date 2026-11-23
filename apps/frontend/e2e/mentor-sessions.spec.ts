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

test.describe("멘토 세션", () => {
  // 시각 표시는 단위 테스트가 시간대별로 확인한다
  test.use({ timezoneId: "Asia/Seoul" });

  test("데스크톱: 메뉴 → 세션 다가오는 탭의 오늘 세션 Meet 입장 (F46·F47)", async ({ page }) => {
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
    await page.route("**/api/v1/me/mentor-assignments**", (route) => route.fulfill({ json: [] }));
    await page.route("**/api/v1/me/mentor-requests**", (route) =>
      route.fulfill({
        json: {
          items: [],
          total: 0,
          limit: 1,
          offset: 0,
          counts: { PENDING: 0, APPROVED: 0, REJECTED: 0, CANCELED: 0 },
        },
      }),
    );
    await page.route("**/api/v1/me/mentor-sessions**", (route) =>
      route.fulfill({
        json: {
          items: [SESSION],
          total: 1,
          limit: 20,
          offset: 0,
          counts: { SCHEDULED: 1, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 },
          view_counts: { upcoming: 1, record_missing: 0, past: 0, all: 1 },
        },
      }),
    );

    await page.goto("/");
    await page.getByRole("navigation", { name: "메뉴", exact: true }).getByRole("link", { name: "세션" }).click();
    await expect(page).toHaveURL(/\/mentor\/sessions$/);
    await expect(page.getByRole("link", { name: "다가오는 1" })).toHaveAttribute("aria-current", "page");
    const row = page.getByRole("table").getByRole("row", { name: /멘토K 멘토링 3회차/ });
    await expect(row).toContainText("11/20(금) 14:00");
    await expect(row.getByRole("link", { name: "Meet 입장" })).toHaveAttribute(
      "href",
      "https://meet.google.com/abc-defg-hij",
    );
  });

  test("휴대폰: 기록 미제출 → [기록 작성] → 상세에서 기록 제출 (F48)", async ({ page }) => {
    await page.clock.setFixedTime(new Date("2026-11-20T08:00:00Z"));
    await page.setViewportSize({ width: 390, height: 844 });
    let current: Record<string, unknown> = { ...SESSION };
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
    await page.route("**/api/v1/me/mentor-assignments**", (route) => route.fulfill({ json: [] }));
    await page.route("**/api/v1/me/mentor-requests**", (route) =>
      route.fulfill({
        json: {
          items: [],
          total: 0,
          limit: 1,
          offset: 0,
          counts: { PENDING: 0, APPROVED: 0, REJECTED: 0, CANCELED: 0 },
        },
      }),
    );
    await page.route("**/api/v1/me/mentor-sessions**", (route) =>
      route.fulfill({
        json: {
          items: [current],
          total: 1,
          limit: 20,
          offset: 0,
          counts: { SCHEDULED: 1, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 },
          view_counts: { upcoming: 0, record_missing: 1, past: 0, all: 1 },
        },
      }),
    );
    await page.route("**/api/v1/mentoring/sessions/s1/note", (route) =>
      route.fulfill({ json: { session_id: "s1", body: null, updated_at: null } }),
    );
    await page.route("**/api/v1/mentoring/sessions/s1/record", async (route) => {
      const body = route.request().postDataJSON() as { duration: number; topic: string; summary: string };
      current = {
        ...current,
        status: "COMPLETED",
        record_duration_minutes: body.duration,
        summary: body.summary,
        recorded_at: "2026-11-20T08:00:00Z",
      };
      return route.fulfill({ json: current });
    });
    await page.route("**/api/v1/mentoring/sessions/s1", (route) => route.fulfill({ json: current }));

    await page.goto("/mentor/sessions?tab=record_missing");
    await page.getByRole("link", { name: "기록 작성" }).click();
    await expect(page.getByRole("heading", { name: "멘토K 멘토링 3회차", level: 1 })).toBeVisible();
    await page.getByRole("textbox", { name: "요약 (수강생도 봐요)" }).fill("README 구성 정리");
    await page.getByRole("button", { name: "기록 제출" }).click();
    await expect(page.getByText("진행함 · 60분 (고정)")).toBeVisible();
  });
});
