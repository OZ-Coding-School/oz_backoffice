import { expect, test } from "@playwright/test";

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
const BASE = {
  team_id: null,
  team_label: null,
  requester_id: "st12",
  requester_name: "가수강",
  mentor_id: "m1",
  mentor_display_name: "멘토K",
  mentor_headline: null,
  detail: "",
  duration: 60,
  reject_reason: null,
  rejected_at: null,
  cancel_reason: null,
  canceled_at: null,
  canceled_by: null,
  session: null,
  balance: { state: "HELD", minutes: 60 },
  replaced_request_id: null,
  created_at: "2026-11-16T01:02:00Z",
  cohort_id: "c12",
  bootcamp_name: "초격차 백엔드",
  cohort_number: 12,
  requester_status: "ENROLLED",
};
const REQUESTS = [
  {
    ...BASE,
    id: "r1",
    status: "PENDING",
    topic: "Django ORM 질문",
    desired_times: ["2026-11-24T10:00:00Z", "2026-11-25T10:00:00Z"],
  },
  {
    ...BASE,
    id: "r2",
    status: "APPROVED",
    topic: "포트폴리오 리뷰",
    desired_times: ["2026-11-20T05:00:00Z"],
    session: { id: "s1", starts_at: "2026-11-20T05:00:00Z", ends_at: "2026-11-20T06:00:00Z" },
    balance: { state: "USED", minutes: 60 },
  },
];

test.describe("멘토 받은 신청", () => {
  // 시각 표시는 단위 테스트가 시간대별로 확인한다
  test.use({ timezoneId: "Asia/Seoul" });

  test("데스크톱: 메뉴 배지 → 받은 신청 대기 탭 → 승인 탭 (F43·F44)", async ({ page }) => {
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
    await page.route("**/api/v1/me/mentor-requests**", (route) => {
      const status = new URL(route.request().url()).searchParams.getAll("status");
      const items = REQUESTS.filter((r) => status.length === 0 || status.includes(r.status));
      return route.fulfill({
        json: {
          items,
          total: items.length,
          limit: 20,
          offset: 0,
          counts: { PENDING: 1, APPROVED: 1, REJECTED: 0, CANCELED: 0 },
        },
      });
    });

    await page.goto("/");
    const menu = page.getByRole("navigation", { name: "메뉴", exact: true });
    await menu.getByRole("link", { name: /받은 신청\s*대기\s*1/ }).click();
    await expect(page).toHaveURL(/\/mentor\/requests$/);
    const table = page.getByRole("table");
    await expect(table.getByRole("row", { name: /Django ORM 질문/ })).toContainText("11/24(화) 19:00 외 1");
    await page.getByRole("link", { name: "승인 1" }).click();
    await expect(page).toHaveURL(/tab=approved/);
    await expect(table.getByRole("row", { name: /포트폴리오 리뷰/ })).toContainText("11/20(금) 14:00");
  });

  test("휴대폰: 카드 → 상세 → 일시 골라 승인 → 처리 결과 (F45)", async ({ page }) => {
    await page.clock.setFixedTime(new Date("2026-11-20T03:00:00Z"));
    await page.setViewportSize({ width: 390, height: 844 });
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
    let current = REQUESTS[0]!;
    await page.route("**/api/v1/me/mentor-requests**", (route) =>
      route.fulfill({
        json: {
          items: current.status === "PENDING" ? [current] : [],
          total: 1,
          limit: 20,
          offset: 0,
          counts: { PENDING: 1, APPROVED: 0, REJECTED: 0, CANCELED: 0 },
        },
      }),
    );
    await page.route("**/api/v1/mentoring/requests/r1", (route) => route.fulfill({ json: current }));
    await page.route("**/api/v1/mentoring/requests/r1/approve", async (route) => {
      const { starts_at } = route.request().postDataJSON() as { starts_at: string };
      current = {
        ...current,
        status: "APPROVED",
        session: { id: "s1", starts_at, ends_at: "2026-11-25T11:00:00Z" },
        balance: { state: "USED", minutes: 60 },
      };
      return route.fulfill({ json: { request: current, session: {} } });
    });

    await page.goto("/mentor/requests");
    await page.getByRole("link", { name: "Django ORM 질문 · 대기" }).click();
    await expect(page.getByRole("heading", { name: "Django ORM 질문", level: 1 })).toBeVisible();
    await page.getByRole("radio", { name: /^2순위/ }).click();
    await page.getByRole("button", { name: "이 일시로 승인" }).click();
    await expect(page.getByRole("heading", { name: "승인한 신청이에요" })).toBeVisible();
    await expect(page.getByText(/11\/25\(수\) 19:00 ~ 20:00 · 2순위/)).toBeVisible();
  });
});
