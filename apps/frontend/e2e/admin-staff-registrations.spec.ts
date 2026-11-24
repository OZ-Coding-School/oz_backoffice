import { expect, test } from "@playwright/test";

const ADMIN = {
  id: "u0",
  email: "boss@nextrunners.co.kr",
  name: "김관리",
  account_type: "STAFF",
  phone_number: null,
  approval_status: "APPROVED",
  approved_at: "2026-11-01T01:00:00Z",
  roles: [{ role: "SUPER_ADMIN", scope_type: "GLOBAL", scope_id: null, expires_at: null }],
};
const ACCESS = {
  permissions: [
    { code: "staff.registration.read", is_global: true, bootcamp_ids: [], cohort_ids: [] },
    { code: "staff.registration.manage", is_global: true, bootcamp_ids: [], cohort_ids: [] },
  ],
  cohorts: [],
};
const OPTIONS = {
  departments: [{ id: "d1", name: "교육운영본부" }],
  teams: [{ id: "t1", department_id: "d1", name: "교육 1팀" }],
  positions: [{ id: "p1", name: "운영 매니저", assignment_scope: "COURSE" }],
  employment_types: ["REGULAR"],
  staff_roles: ["MANAGER", "ASSISTANT"],
  bootcamps: [{ id: "b1", name: "백엔드 부트캠프", code: "BE", team_id: "t1" }],
  cohorts: [],
};
const REG = {
  id: "r1",
  status: "PENDING",
  department_id: "d1",
  team_id: "t1",
  position_id: "p1",
  employment_type: "REGULAR",
  assignments: [{ role: "MANAGER", bootcamp_id: "b1", cohort_id: null }],
  reviewed_at: null,
  reject_reason: null,
  created_at: "2026-11-18T01:00:00Z",
  applicant: { id: "u1", email: "manager@nextrunners.co.kr", name: "김운영", approval_status: "PENDING" },
};

test("운영진 승인: 메뉴 → 검토 → 승인 (FE-15b)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let approved = false;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/me/staff-registration/options", (route) => route.fulfill({ json: OPTIONS }));
  await page.route("**/api/v1/admin/staff-registrations?**", (route) => {
    const pending = new URL(route.request().url()).searchParams.get("status") === "PENDING";
    const items = pending && !approved ? [REG] : [];
    return route.fulfill({ json: { items, total: items.length, limit: 20, offset: 0 } });
  });
  await page.route("**/api/v1/admin/staff-registrations/r1/approve", (route) => {
    approved = true;
    return route.fulfill({ json: { ...REG, status: "APPROVED" } });
  });

  await page.goto("/admin");
  await page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "회원" }).click();
  await expect(page.getByRole("heading", { name: "운영진 승인", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "김운영 검토" }).click();
  await page.getByRole("dialog", { name: "운영진 승인 · 김운영" }).getByRole("button", { name: "승인" }).click();
  await expect(page.getByText("김운영님을 운영진으로 승인했어요")).toBeVisible();
  await expect(page.getByRole("heading", { name: "처리할 운영진 신청이 없어요" })).toBeVisible();
});
