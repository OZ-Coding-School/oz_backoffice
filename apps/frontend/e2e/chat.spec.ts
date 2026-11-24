import { expect, test, type Page } from "@playwright/test";

const ME = {
  id: "u1",
  email: "student@gmail.com",
  name: "가수강",
  account_type: "STUDENT",
  phone_number: "01012345678",
  approval_status: "APPROVED",
  approved_at: "2026-11-16T01:00:00Z",
  is_super_admin: false,
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
const THREAD = {
  id: "th1",
  kind: "DIRECT",
  cohort_id: "c12",
  student_id: "st12",
  student_name: "가수강",
  team_id: null,
  team_label: null,
  mentor_id: "m1",
  mentor_display_name: "멘토K",
  last_message_at: "2026-11-16T01:00:00Z",
  last_message: null,
  unread_count: 0,
};
const msg = (id: string, body: string, mine: boolean) => ({
  id,
  thread_id: "th1",
  sender_kind: mine ? "STUDENT" : "MENTOR",
  sender_id: mine ? "u1" : "mu1",
  sender_name: mine ? "가수강" : "멘토K",
  body,
  is_deleted: false,
  created_at: "2026-11-15T00:20:00Z",
});

async function mockApi(page: Page) {
  const messages = [msg("m2", "확인했어요.", false), msg("m1", "README 링크 미리 공유드려요!", true)];
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ME }));
  await page.route("**/api/v1/me/enrollments", (route) => route.fulfill({ json: [ENROLLMENT] }));
  await page.route("**/api/v1/me/mentoring/chat/threads**", (route) =>
    route.fulfill({ json: { items: [{ ...THREAD, unread_count: 2 }], total: 1, limit: 50, offset: 0 } }),
  );
  await page.route("**/api/v1/mentoring/chat/threads/th1/read", (route) => route.fulfill({ json: THREAD }));
  await page.route("**/api/v1/mentoring/chat/threads/th1", (route) => route.fulfill({ json: THREAD }));
  await page.route("**/api/v1/me/mentoring/chat/stream", (route) =>
    route.fulfill({ headers: { "Content-Type": "text/event-stream" }, body: "event: ready\ndata: {}\n\n" }),
  );
  await page.route("**/api/v1/mentoring/chat/threads/th1/messages**", async (route) => {
    if (route.request().method() === "POST") {
      const { body } = route.request().postDataJSON() as { body: string };
      const sent = { ...msg("m3", body, true), created_at: "2026-11-16T02:00:00Z" };
      messages.unshift(sent);
      return route.fulfill({ status: 201, json: sent });
    }
    return route.fulfill({ json: { items: messages, next_before: null } });
  });
}

test("데스크톱: 채팅 방을 골라 Enter로 보내기 (F40)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await mockApi(page);
  await page.goto("/mentoring/chat");
  await expect(page.getByText("대화를 골라 주세요")).toBeVisible();
  await page.getByRole("link", { name: "멘토K" }).click();
  const convo = page.getByRole("region", { name: "멘토K" });
  await expect(convo.getByText("확인했어요.")).toBeVisible();
  await convo.getByRole("textbox", { name: "메시지" }).fill("감사합니다");
  await convo.getByRole("textbox", { name: "메시지" }).press("Enter");
  await expect(convo.getByText("감사합니다")).toBeVisible();
});

test("휴대폰: 방 목록 → 전체 화면 대화 → 뒤로 (F40)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockApi(page);
  await page.goto("/mentoring/chat");
  await page.getByRole("link", { name: "멘토K" }).click();
  await expect(page.getByRole("region", { name: "멘토K" }).getByText("확인했어요.")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "하단 메뉴" })).toBeHidden();
  await page.getByRole("link", { name: "방 목록" }).click();
  await expect(page.getByRole("region", { name: "채팅" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "하단 메뉴" })).toBeVisible();
});

test("데스크톱: 메뉴의 채팅에 안 읽음 수를 보여 준다 (F41)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await mockApi(page);
  await page.goto("/");
  const menu = page.getByRole("navigation", { name: "메뉴", exact: true }).first();
  await expect(menu.getByRole("link", { name: /채팅/ })).toContainText("안 읽음 2");
});
