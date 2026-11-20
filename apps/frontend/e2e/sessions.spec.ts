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
const REQUEST = {
  // 승인된 신청 (세션 s1)
  id: "r1",
  status: "APPROVED",
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
  session: { id: "s1", starts_at: "2026-11-20T05:00:00Z", ends_at: "2026-11-20T06:00:00Z" },
  balance: { state: "USED", minutes: 60 },
  replaced_request_id: null,
  created_at: "2026-11-16T01:02:00Z",
};

const SCHEDULED = {
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
  mentor_headline: "네이버 백엔드 7년차",
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
const COMPLETED = {
  ...SCHEDULED,
  id: "s2",
  status: "COMPLETED",
  title: "멘토K 멘토링 2회차",
  topic: "README 구성",
  starts_at: "2026-11-16T01:00:00Z",
  ends_at: "2026-11-16T02:00:00Z",
  actual_started_at: "2026-11-16T01:02:00Z",
  actual_ended_at: "2026-11-16T02:01:00Z",
  balance: { state: "USED", minutes: 60 },
  google_meet_url: null,
  summary: "## 오늘 다룬 것\n\n- README 첫 화면 정리",
  record_duration_minutes: 60,
  recorded_at: "2026-11-16T02:20:00Z",
};

async function mockApi(page: Page) {
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ME }));
  await page.route("**/api/v1/me/enrollments", (route) => route.fulfill({ json: [ENROLLMENT] }));
  await page.route("**/api/v1/me/balances", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/me/mentoring/sessions**", (route) => {
    const statuses = new URL(route.request().url()).searchParams.getAll("status");
    const items = [SCHEDULED, COMPLETED].filter((s) => statuses.length === 0 || statuses.includes(s.status));
    route.fulfill({
      json: {
        items,
        total: items.length,
        limit: 20,
        offset: 0,
        counts: { SCHEDULED: 1, IN_PROGRESS: 0, COMPLETED: 1, NO_SHOW: 0, CANCELED: 0 },
      },
    });
  });
  await page.route("**/api/v1/mentoring/sessions/s1", (route) => route.fulfill({ json: SCHEDULED }));
  await page.route("**/api/v1/mentoring/sessions/s2", (route) => route.fulfill({ json: COMPLETED }));
  await page.route("**/api/v1/mentoring/requests/r1", (route) => route.fulfill({ json: REQUEST }));
}

test("데스크톱: 진행 기록 → 예정 탭 → 세션 상세의 Meet 입장·신청 보기 (F33·F34)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("navigation", { name: "메뉴", exact: true }).getByRole("link", { name: "진행 기록" }).click();
  await expect(page.getByRole("link", { name: "전체 2" })).toHaveAttribute("aria-current", "page");
  await page.getByRole("link", { name: "예정 1" }).click();
  await expect(page.getByRole("link", { name: "멘토K 멘토링 2회차 · 완료" })).toHaveCount(0);
  await page.getByRole("link", { name: "멘토K 멘토링 3회차 · 예정" }).click();

  await expect(page.getByRole("heading", { name: "멘토K 멘토링 3회차", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Meet 입장" })).toHaveAttribute(
    "href",
    "https://meet.google.com/abc-defg-hij",
  );
  await page.getByRole("link", { name: "신청 보기" }).click();
  await expect(page).toHaveURL(/\/mentoring\/requests\/r1$/);
});

test("휴대폰: 하단 탭 → 완료 세션의 멘토 기록 (F33)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("navigation", { name: "하단 메뉴" }).getByRole("link", { name: "진행 기록" }).click();
  await page.getByRole("link", { name: "멘토K 멘토링 2회차 · 완료" }).click();
  const record = page.getByRole("region", { name: "멘토 기록" });
  await expect(record.getByRole("heading", { name: "오늘 다룬 것" })).toBeVisible();
  await expect(page.getByText("1시간 차감 · 추가 차감 없음")).toBeVisible();
});
