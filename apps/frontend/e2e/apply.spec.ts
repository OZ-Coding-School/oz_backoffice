import { expect, test } from "@playwright/test";

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

test("휴대폰: 하단 탭 '신청'으로 1:1 멘토링을 신청하고 완료 화면에서 상세로 간다 (F30)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  // 3일 뒤 10:00~12:00 KST가 비어 있다
  const day = new Date(Date.now() + 3 * 86_400_000);
  day.setUTCHours(1, 0, 0, 0);
  const interval = { starts_at: day.toISOString(), ends_at: new Date(day.getTime() + 2 * 3_600_000).toISOString() };
  let created: Record<string, unknown> | null = null;
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
        allowed_duration: 60,
        min_lead_hours: 24,
        max_pending_requests: 3,
      },
    }),
  );
  await page.route("**/api/v1/me/balances", (route) =>
    route.fulfill({
      json: [
        {
          id: "a1",
          owner_type: "STUDENT",
          owner_id: "st12",
          owner_name: "가수강",
          valid_from: "2026-10-01",
          valid_until: "2027-03-31",
          is_expired: false,
          total_minutes: 180,
          held_minutes: 0,
          used_minutes: 0,
          remaining_minutes: 180,
        },
      ],
    }),
  );
  await page.route("**/api/v1/me/mentoring/mentors**", (route) =>
    route.fulfill({
      json: [
        {
          mentor_id: "m1",
          display_name: "멘토K",
          headline: "네이버 백엔드",
          expertise: "Python",
          profile_image_url: null,
        },
      ],
    }),
  );
  await page.route("**/api/v1/mentors/m1/available-times**", (route) =>
    route.fulfill({
      json: {
        mentor_id: "m1",
        cohort_id: "c12",
        accepting_requests: true,
        allowed_duration: 60,
        min_lead_hours: 24,
        intervals: [interval],
      },
    }),
  );
  await page.route("**/api/v1/mentoring/requests", (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    created = {
      ...body,
      id: "r9",
      status: "PENDING",
      team_label: null,
      requester_id: "st12",
      requester_name: "가수강",
      mentor_display_name: "멘토K",
      mentor_headline: "네이버 백엔드",
      reject_reason: null,
      rejected_at: null,
      cancel_reason: null,
      canceled_at: null,
      canceled_by: null,
      session: null,
      balance: { state: "HELD", minutes: 60 },
      replaced_request_id: null,
      created_at: new Date().toISOString(),
    };
    return route.fulfill({ status: 201, json: created });
  });
  await page.route("**/api/v1/mentoring/requests/r9", (route) => route.fulfill({ json: created }));

  await page.goto("/");
  await page.getByRole("navigation", { name: "하단 메뉴" }).getByRole("link", { name: "신청", exact: true }).click();
  await page.getByRole("radio", { name: /멘토K/ }).click();
  await page.getByRole("button", { name: "다음: 일정 선택" }).click();
  await page.getByRole("button", { name: "10:00" }).click();
  await page.getByRole("button", { name: "다음: 신청 내용" }).click();
  await page.getByRole("textbox", { name: "주제" }).fill("포트폴리오 리뷰");
  await page.getByRole("textbox", { name: "상세 내용" }).fill("## 질문\n- README");
  await page.getByRole("button", { name: "다음: 신청 확인" }).click();
  await page.reload(); // 새로고침해도 고른 값이 남는다
  await expect(page.getByText("포트폴리오 리뷰")).toBeVisible();
  await page.getByRole("button", { name: "신청하기" }).click();
  await expect(page.getByRole("heading", { name: "신청했어요" })).toBeVisible();
  await page.getByRole("link", { name: "내 신청 보기" }).click();
  await expect(page.getByRole("heading", { name: "포트폴리오 리뷰", level: 1 })).toBeVisible();
});
