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
    { code: "staff.assignment.read", is_global: true, bootcamp_ids: [], cohort_ids: [] },
    { code: "staff.assignment.manage", is_global: true, bootcamp_ids: [], cohort_ids: [] },
  ],
  cohorts: [
    {
      id: "c12",
      bootcamp_id: "b1",
      bootcamp_name: "백엔드 부트캠프",
      cohort_number: 12,
      start_date: "2026-11-01",
      end_date: "2027-04-30",
      status: "ONGOING",
    },
  ],
};
const OPTIONS = {
  departments: [{ id: "d1", name: "교육운영본부" }],
  teams: [{ id: "t1", department_id: "d1", name: "교육 1팀" }],
  positions: [{ id: "p2", name: "조교", assignment_scope: "COHORT" }],
  employment_types: ["REGULAR"],
  staff_roles: ["MANAGER", "ASSISTANT"],
  bootcamps: [{ id: "b1", name: "백엔드 부트캠프", code: "BE", team_id: "t1" }],
  cohorts: [],
};
const LEE = {
  id: "e2",
  user: { id: "u2", email: "lee@nextrunners.co.kr", name: "이조교" },
  department_id: "d1",
  team_id: "t1",
  position_id: "p2",
  employment_type: "REGULAR",
  assignments: [],
};

test("담당자 탭: 과정·기수 고르고 조교 추가 (FE-15c)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const members: unknown[] = [];
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/me/staff-registration/options", (route) => route.fulfill({ json: OPTIONS }));
  await page.route("**/api/v1/admin/employees?**", (route) =>
    route.fulfill({ json: { items: [LEE], total: 1, limit: 20, offset: 0 } }),
  );
  await page.route("**/api/v1/admin/bootcamps/b1/staffs", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/admin/cohorts/c12/staffs", (route) => {
    if (route.request().method() === "POST") {
      const m = { id: "cs1", employee_id: "e2", role: "ASSISTANT", user: LEE.user, created_at: "2026-11-24T01:00:00Z" };
      members.push(m);
      return route.fulfill({ status: 201, json: m });
    }
    return route.fulfill({ json: members });
  });

  await page.goto("/admin/members/staff?tab=staff");
  await page.getByRole("combobox", { name: "과정" }).click();
  await page.getByRole("option", { name: "백엔드 부트캠프" }).click();
  await page.getByRole("combobox", { name: "기수" }).click();
  await page.getByRole("option", { name: "12기" }).click();
  await expect(page.getByRole("heading", { name: "백엔드 부트캠프 12기 담당자가 없어요" })).toBeVisible();
  await page.getByRole("button", { name: "담당자 추가" }).click();
  const dialog = page.getByRole("dialog", { name: "담당자 추가" });
  await dialog.getByRole("radio", { name: "이조교" }).click();
  await dialog.getByRole("button", { name: "추가" }).click();
  await expect(page.getByRole("table", { name: "백엔드 부트캠프 12기 담당자" })).toContainText("이조교");
});
