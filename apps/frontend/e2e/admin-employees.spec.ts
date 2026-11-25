import { expect, test } from "@playwright/test";

const ADMIN = {
  id: "u0",
  email: "boss@nextrunners.co.kr",
  name: "김관리",
  account_type: "STAFF",
  phone_number: null,
  approval_status: "APPROVED",
  approved_at: "2026-11-01T01:00:00Z",
  is_super_admin: true,
};
const ACCESS = {
  is_super_admin: true,
  position: null,
  permissions: ["org.employee.read", "org.employee.manage", "staff.assignment.read", "staff.assignment.manage"].map(
    (code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] }),
  ),
  cohorts: [],
};
const OPTIONS = {
  departments: [{ id: "d1", name: "교육운영본부" }],
  teams: [{ id: "t1", department_id: "d1", name: "교육 1팀" }],
  positions: [{ id: "p1", name: "운영 매니저", assignment_scope: "COURSE" }],
  employment_types: ["REGULAR", "CONTRACT"],
  bootcamps: [{ id: "b1", name: "백엔드 부트캠프", code: "BE", team_id: "t1" }],
  cohorts: [],
};
const KIM = {
  id: "e1",
  user: { id: "u1", email: "manager@nextrunners.co.kr", name: "김운영" },
  department_id: "d1",
  team_id: "t1",
  position_id: "p1",
  employment_type: "REGULAR",
  assignments: [],
  is_super_admin: false,
  data_scope: "ASSIGNED",
};

test("조직 설정 > 직원: 행 → 패널 → 수정 → 저장 (FE-15f)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let saved: Record<string, unknown> | null = null;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/me/staff-registration/options", (route) => route.fulfill({ json: OPTIONS }));
  await page.route("**/api/v1/admin/employees", (route) =>
    route.fulfill({ json: [saved ? { ...KIM, ...saved } : KIM] }),
  );
  await page.route("**/api/v1/admin/employees/e1", async (route) => {
    saved = route.request().postDataJSON() as Record<string, unknown>;
    return route.fulfill({ json: { ...KIM, ...saved } });
  });

  await page.goto("/admin");
  await page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "조직" }).click();
  await expect(page.getByRole("heading", { name: "직원", level: 1 })).toBeVisible();
  await page.getByRole("link", { name: "김운영" }).click();
  const sheet = page.getByRole("dialog", { name: "김운영" });
  await sheet.getByRole("button", { name: "수정" }).click();
  await sheet.getByRole("combobox", { name: "고용 형태" }).click();
  await page.getByRole("option", { name: "계약직" }).click();
  await sheet.getByRole("button", { name: "저장" }).click();
  await expect(page.getByText("김운영님 정보를 저장했어요")).toBeVisible();
  await expect(sheet.getByRole("region", { name: "소속" })).toContainText("계약직");
  expect(saved).toEqual({ employment_type: "CONTRACT" });
});
