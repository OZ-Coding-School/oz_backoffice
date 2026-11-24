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

test.describe("멘토 일정", () => {
  // 시각 표시는 단위 테스트가 시간대별로 확인한다
  test.use({ timezoneId: "Asia/Seoul" });

  test("휴대폰: 하루 보기에서 요일 칩으로 날짜를 바꾸고 신청 받기를 확인 후 끈다 (F51·F52)", async ({ page }) => {
    await page.clock.setFixedTime(new Date("2026-11-24T03:00:00Z"));
    await page.setViewportSize({ width: 390, height: 844 });
    let accepting = true;
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
          limit: 1,
          offset: 0,
          counts: { PENDING: 0, APPROVED: 0, REJECTED: 0, CANCELED: 0 },
        },
      }),
    );
    await page.route("**/api/v1/me/mentor-sessions**", (route) =>
      route.fulfill({
        json: {
          items: [],
          total: 0,
          limit: 100,
          offset: 0,
          counts: { SCHEDULED: 0, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 },
          view_counts: { upcoming: 0, record_missing: 0, past: 0, all: 0 },
        },
      }),
    );
    await page.route("**/api/v1/me/mentor-schedule/accepting", async (route) => {
      accepting = (route.request().postDataJSON() as { accepting_requests: boolean }).accepting_requests;
      return route.fulfill({ json: { mentor_id: "m1", accepting_requests: accepting, canceled_pending_requests: 1 } });
    });
    await page.route("**/api/v1/me/mentor-schedule", (route) =>
      route.fulfill({
        json: {
          mentor_id: "m1",
          accepting_requests: accepting,
          unavailable_periods: [
            {
              id: "p1",
              mentor_id: "m1",
              repeat: "WEEKLY",
              starts_at: "2026-11-03T00:00:00Z",
              ends_at: "2026-11-03T03:00:00Z",
              all_day: false,
              weekdays: [2],
              repeat_until: null,
              category: "본업",
              reason: null,
            },
          ],
        },
      }),
    );

    await page.goto("/");
    // 멘토 메뉴가 6개라 일정은 더보기 안에 있다 (F54)
    await page.getByRole("navigation", { name: "하단 메뉴" }).getByRole("button", { name: "더보기" }).click();
    await page.getByRole("dialog", { name: "더보기" }).getByRole("link", { name: "일정" }).click();
    await expect(page).toHaveURL(/\/mentor\/schedule$/);
    const tuesday = page.getByRole("group", { name: "11월 24일 (화)" });
    await expect(tuesday.getByText("본업 · 매주")).toBeVisible();
    await page.getByRole("tab", { name: "11월 25일 (수)" }).click();
    await expect(page.getByRole("group", { name: "11월 25일 (수)" })).toBeVisible();
    await expect(tuesday).toBeHidden();

    await page.getByRole("switch", { name: "신청 받기" }).click();
    await page.getByRole("dialog", { name: "신청 받기를 끌까요?" }).getByRole("button", { name: "끄기" }).click();
    await expect(page.getByText("신청 받기를 껐어요. 대기 중인 신청 1건을 취소했어요")).toBeVisible();
  });

  test("데스크톱: 불가 시간 추가 → 충돌 확인 → 그래도 저장 (F53)", async ({ page }) => {
    await page.clock.setFixedTime(new Date("2026-11-24T03:00:00Z"));
    await page.setViewportSize({ width: 1440, height: 900 });
    const confirms: (string | null)[] = [];
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
          limit: 1,
          offset: 0,
          counts: { PENDING: 0, APPROVED: 0, REJECTED: 0, CANCELED: 0 },
        },
      }),
    );
    await page.route("**/api/v1/me/mentor-sessions**", (route) =>
      route.fulfill({
        json: {
          items: [],
          total: 0,
          limit: 100,
          offset: 0,
          counts: { SCHEDULED: 0, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 },
          view_counts: { upcoming: 0, record_missing: 0, past: 0, all: 0 },
        },
      }),
    );
    await page.route("**/api/v1/me/mentor-schedule/unavailable-periods**", async (route) => {
      const confirm = new URL(route.request().url()).searchParams.get("confirm");
      confirms.push(confirm);
      const applied = confirm === "true";
      return route.fulfill({
        status: applied ? 201 : 200,
        json: {
          applied,
          unavailable_period: {
            id: "p9",
            mentor_id: "m1",
            repeat: "ONCE",
            starts_at: "2026-11-24T00:00:00Z",
            ends_at: "2026-11-24T01:00:00Z",
            all_day: false,
            weekdays: [],
            repeat_until: null,
            category: null,
            reason: null,
          },
          conflicts: [
            {
              kind: "SESSION",
              target_id: "s1",
              starts_at: "2026-11-24T00:00:00Z",
              ends_at: "2026-11-24T01:00:00Z",
              topic: "팀 프로젝트 API 설계 리뷰",
              requester_label: "3팀 알파",
            },
          ],
        },
      });
    });
    await page.route("**/api/v1/me/mentor-schedule", (route) =>
      route.fulfill({ json: { mentor_id: "m1", accepting_requests: true, unavailable_periods: [] } }),
    );

    await page.goto("/mentor/schedule");
    await page.getByRole("button", { name: "불가 시간 추가" }).click();
    const dialog = page.getByRole("dialog", { name: "불가 시간 추가" });
    await dialog.getByRole("button", { name: "저장" }).click();
    const conflict = page.getByRole("dialog", { name: "겹치는 일정이 1건 있어요" });
    await expect(conflict.getByText("승인 세션 → 취소·환불")).toBeVisible();
    await conflict.getByRole("button", { name: "그래도 저장" }).click();
    await expect(page.getByText("저장했어요. 겹친 일정 1건을 정리했어요")).toBeVisible();
    expect(confirms).toEqual(["false", "true"]);
  });
});
