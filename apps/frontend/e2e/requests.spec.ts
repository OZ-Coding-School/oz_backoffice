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
const REQUEST = {
  id: "r1",
  status: "PENDING",
  team_id: null,
  team_label: null,
  requester_id: "st12",
  requester_name: "가수강",
  mentor_id: "m1",
  mentor_display_name: "멘토K",
  mentor_headline: "네이버 백엔드 7년차",
  topic: "Django ORM 질문",
  detail: "## 질문 정리\n\n- N+1 문제",
  desired_times: ["2026-11-24T10:00:00Z"],
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
};

async function mockApi(page: Page) {
  let current: Record<string, unknown> = REQUEST;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ME }));
  await page.route("**/api/v1/me/enrollments", (route) => route.fulfill({ json: [ENROLLMENT] }));
  await page.route("**/api/v1/me/balances", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/me/mentoring/requests**", (route) => {
    const canceled = current.status === "CANCELED";
    route.fulfill({
      json: {
        items: [current],
        total: 1,
        limit: 20,
        offset: 0,
        counts: { PENDING: canceled ? 0 : 1, APPROVED: 0, REJECTED: 0, CANCELED: canceled ? 1 : 0 },
      },
    });
  });
  await page.route("**/api/v1/mentoring/requests/r1", (route) => route.fulfill({ json: current }));
  await page.route("**/api/v1/mentoring/requests/r1/cancel", (route) => {
    current = {
      ...REQUEST,
      status: "CANCELED",
      cancel_reason: "일정이 바뀌었어요",
      canceled_at: "2026-11-17T01:00:00Z",
      canceled_by: "REQUESTER",
      balance: { state: "RETURNED", minutes: 60 },
    };
    return route.fulfill({ json: current });
  });
}

test("휴대폰: 하단 탭으로 신청 내역 → 상세 → 사유를 적어 취소 (F29)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("navigation", { name: "하단 메뉴" }).getByRole("link", { name: "신청 내역" }).click();
  await expect(page.getByRole("link", { name: "전체 1" })).toHaveAttribute("aria-current", "page");
  await page.getByRole("link", { name: "Django ORM 질문 · 승인 대기" }).click();
  await expect(page.getByRole("heading", { name: "Django ORM 질문", level: 1 })).toBeVisible();

  await page.getByRole("button", { name: "신청 취소" }).click();
  const dialog = page.getByRole("dialog", { name: "이 신청을 취소할까요?" });
  await dialog.getByLabel("취소 사유 (멘토에게 보여요)").fill("일정이 바뀌었어요");
  await dialog.getByRole("button", { name: "신청 취소" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByText("취소 사유 · 일정이 바뀌었어요 (11/17 10:00 본인 취소)")).toBeVisible();

  await page.getByRole("link", { name: "신청 내역" }).first().click();
  await expect(page.getByRole("link", { name: "반려·취소 1" })).toBeVisible();
});
