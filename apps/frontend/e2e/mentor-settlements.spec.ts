import { expect, test, type Page } from "@playwright/test";

const MENTOR = {
  id: "u9",
  email: "mentor@gmail.com",
  name: "김멘토",
  account_type: "MENTOR",
  phone_number: "01012345678",
  approval_status: "APPROVED",
  approved_at: "2026-11-01T01:00:00Z",
  is_super_admin: false,
};
const SUMMARY = {
  id: "st1",
  mentor_id: "m1",
  mentor_name: "김멘토",
  cohort_id: "c12",
  bootcamp_name: "초격차 백엔드",
  cohort_number: 12,
  month: "2026-10",
  status: "CLOSED",
  session_count: 2,
  total_minutes: 150,
  total_amount: 75000,
  closed_at: "2026-11-05T01:00:00Z",
};
const ITEM = {
  session_starts_at: "2026-10-28T10:00:00Z",
  session_topic: "포트폴리오 방향",
  team_label: null,
  requester_name: "가수강",
  item_type: "SESSION",
  settlement_policy: "ACTUAL_DURATION",
  pay_unit: "HOURLY",
  pay_rate: 30000,
  uncharged_overtime_minutes: null,
};
const DETAIL = {
  ...SUMMARY,
  items: [
    { ...ITEM, session_id: "s1", billable_minutes: 60, amount: 30000 },
    {
      ...ITEM,
      session_id: "s2",
      session_starts_at: "2026-10-24T01:00:00Z",
      session_topic: "ERD 리뷰",
      team_label: "3팀 알파",
      billable_minutes: 90,
      amount: 45000,
    },
  ],
};

async function mockMentor(page: Page) {
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
      json: { items: [], total: 0, limit: 1, offset: 0, counts: { PENDING: 0, APPROVED: 0, REJECTED: 0, CANCELED: 0 } },
    }),
  );
  await page.route("**/api/v1/me/mentor-sessions**", (route) =>
    route.fulfill({
      json: {
        items: [],
        total: 0,
        limit: 20,
        offset: 0,
        counts: { SCHEDULED: 0, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 },
        view_counts: { upcoming: 0, record_missing: 0, past: 0, all: 0 },
      },
    }),
  );
  await page.route("**/api/v1/me/mentor-settlements", (route) => route.fulfill({ json: [SUMMARY] }));
  await page.route("**/api/v1/me/mentor-settlements/st1", (route) => route.fulfill({ json: DETAIL }));
}

test.describe("멘토 정산", () => {
  // 시각 표시는 단위 테스트가 시간대별로 확인한다
  test.use({ timezoneId: "Asia/Seoul" });

  test("데스크톱: 메뉴 → 정산 → 정산서 명세 (F54)", async ({ page }) => {
    await page.clock.setFixedTime(new Date("2026-11-20T03:00:00Z"));
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockMentor(page);

    await page.goto("/");
    await page.getByRole("navigation", { name: "메뉴", exact: true }).getByRole("link", { name: "정산" }).click();
    await expect(page).toHaveURL(/\/mentor\/settlements$/);
    await expect(page.getByRole("list", { name: "정산 요약" })).toContainText("10월 정산 합계75,000원");
    await page.getByRole("table").getByRole("link", { name: "초격차 백엔드 12기" }).click();
    await expect(page.getByRole("heading", { name: "2026년 10월 · 초격차 백엔드 12기", level: 1 })).toBeVisible();
    await expect(page.getByRole("table").getByRole("row", { name: /3팀 알파 · 팀/ })).toContainText("45,000원");
  });

  test("휴대폰: 하단 탭은 채팅 고정, 더보기 → 정산 → 카드 (F54)", async ({ page }) => {
    await page.clock.setFixedTime(new Date("2026-11-20T03:00:00Z"));
    await page.setViewportSize({ width: 390, height: 844 });
    await mockMentor(page);

    await page.goto("/");
    const tabs = page.getByRole("navigation", { name: "하단 메뉴" });
    await expect(tabs.getByRole("link", { name: "채팅" })).toBeVisible();
    await tabs.getByRole("button", { name: "더보기" }).click();
    await page.getByRole("dialog", { name: "더보기" }).getByRole("link", { name: "정산" }).click();
    await expect(page).toHaveURL(/\/mentor\/settlements$/);
    await page.getByRole("link", { name: "2026-10 · 초격차 백엔드 12기" }).click();
    await expect(page.getByRole("article", { name: /가수강 · 1:1/ })).toContainText("60분 · 30,000원/시간");
  });
});
