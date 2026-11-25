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
  permissions: ["org.department.read", "org.department.manage"].map((code) => ({
    code,
    is_global: true,
    bootcamp_ids: [],
    cohort_ids: [],
  })),
  cohorts: [],
};
const OPTIONS = {
  departments: [],
  teams: [],
  positions: [],
  employment_types: [],
  bootcamps: [{ id: "b1", name: "백엔드 부트캠프", code: "BE", team_id: "t1" }],
  cohorts: [],
};
const DEPARTMENTS = [
  { id: "d1", name: "교육운영본부", description: "운영", rules: null, employee_count: 3 },
  { id: "d2", name: "경영지원본부", description: "지원", rules: null, employee_count: 0 },
];
const TEAM = {
  id: "t1",
  department_id: "d1",
  name: "교육 1팀",
  description: null,
  bootcamp_ids: ["b1"],
  employee_count: 3,
};

test("조직 설정 > 부서: 조직도 → 팀 → 부서 옮기기 확인 → 저장 (FE-15g)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let saved: Record<string, unknown> | null = null;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/me/staff-registration/options", (route) => route.fulfill({ json: OPTIONS }));
  await page.route("**/api/v1/admin/departments", (route) => route.fulfill({ json: DEPARTMENTS }));
  await page.route("**/api/v1/admin/teams", (route) => route.fulfill({ json: [saved ? { ...TEAM, ...saved } : TEAM] }));
  await page.route("**/api/v1/admin/teams/t1/impact", (route) =>
    route.fulfill({
      json: {
        employees: [
          {
            id: "e1",
            user_id: "u1",
            name: "김운영",
            email: "manager@nextrunners.co.kr",
            department_name: "교육운영본부",
            team_name: "교육 1팀",
            position_name: "운영 매니저",
          },
        ],
        registrations: [],
        teams: [],
        bootcamps: [],
      },
    }),
  );
  await page.route("**/api/v1/admin/teams/t1", async (route) => {
    saved = route.request().postDataJSON() as Record<string, unknown>;
    return route.fulfill({ json: { ...TEAM, ...saved } });
  });

  await page.goto("/admin");
  await page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "조직" }).click();
  await expect(page.getByRole("heading", { name: "부서", level: 1 })).toBeVisible();
  await page.getByRole("navigation", { name: "보기" }).getByRole("link", { name: "트리" }).click();
  await page.getByRole("region", { name: "조직도" }).getByRole("link", { name: "교육 1팀" }).click();
  const sheet = page.getByRole("dialog", { name: "교육 1팀" });
  await sheet.getByRole("button", { name: "수정" }).click();
  await sheet.getByRole("combobox", { name: "부서" }).click();
  await page.getByRole("option", { name: "경영지원본부" }).click();
  await sheet.getByRole("button", { name: "저장" }).click();
  const confirm = page.getByRole("dialog", { name: "교육 1팀을 경영지원본부로 옮길까요?" });
  await confirm.getByRole("button", { name: /직원/ }).click();
  await expect(confirm.getByRole("list", { name: "직원" })).toContainText("김운영");
  await confirm.getByRole("button", { name: "옮기고 저장" }).click();
  await expect(page.getByText("교육 1팀 팀을 저장했어요")).toBeVisible();
  expect(saved).toMatchObject({ department_id: "d2" });
});
