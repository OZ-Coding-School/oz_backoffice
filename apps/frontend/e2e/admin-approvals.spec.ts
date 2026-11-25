import { expect, test } from "@playwright/test";

const STAFF = {
  id: "u0",
  email: "staff@nextrunners.co.kr",
  name: "김운영",
  account_type: "STAFF",
  phone_number: null,
  approval_status: "APPROVED",
  approved_at: "2026-11-01T01:00:00Z",
  is_super_admin: true,
};
const ACCESS = {
  is_super_admin: false,
  position: null,
  permissions: [
    { code: "member.approval.read", is_global: true, bootcamp_ids: [], cohort_ids: [] },
    { code: "member.approval.manage", is_global: true, bootcamp_ids: [], cohort_ids: [] },
  ],
  cohorts: [],
};
const APPLICANT = {
  user_id: "u1",
  name: "가수강",
  email: "student@example.com",
  phone_number: "01012341234",
  approval_status: "PENDING",
  signup: {
    id: "sg1",
    signup_type: "STUDENT",
    status: "PENDING",
    requested_cohort_id: "c12",
    nickname: null,
    display_name_preference: null,
    match_result: "NO_MATCH",
    reject_reason: null,
    reviewed_at: null,
    created_at: "2026-11-16T01:00:00Z",
  },
  requested_bootcamp_name: "백엔드",
  requested_cohort_number: 12,
};

test("운영진: 메뉴 → 가입 승인 → 명단을 골라 승인 (FE-15a)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let approved = false;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: STAFF }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/admin/approvals?**", (route) => {
    const items =
      approved || new URL(route.request().url()).searchParams.get("signup_type") === "MENTOR" ? [] : [APPLICANT];
    return route.fulfill({ json: { items, total: items.length, limit: 20, offset: 0 } });
  });
  await page.route("**/api/v1/admin/approvals/u1/candidates**", (route) =>
    route.fulfill({
      json: {
        signup_type: "STUDENT",
        contracts: [],
        mentors: [],
        students: [
          {
            student_id: "st1",
            name: "가수강",
            phone_number: "01012341234",
            cohort_id: "c12",
            bootcamp_name: "백엔드",
            cohort_number: 12,
            enrollment_status: "ENROLLED",
            name_match: true,
            phone_match: true,
            same_cohort: true,
          },
        ],
      },
    }),
  );
  await page.route("**/api/v1/admin/approvals/u1/approve", (route) => {
    approved = true;
    return route.fulfill({ json: { ...APPLICANT, approval_status: "APPROVED" } });
  });

  await page.goto("/admin");
  await page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "회원" }).click();
  await expect(page.getByRole("heading", { name: "가입 승인", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "가수강 승인" }).click();
  const dialog = page.getByRole("dialog", { name: "가입 승인 · 가수강" });
  await dialog.getByRole("radio", { name: "가수강 백엔드 12기" }).click();
  await dialog.getByRole("button", { name: "연결하고 승인" }).click();
  await expect(page.getByText("가수강님 가입을 승인했어요")).toBeVisible();
  await expect(page.getByRole("heading", { name: "처리할 가입 신청이 없어요" })).toBeVisible();
});
