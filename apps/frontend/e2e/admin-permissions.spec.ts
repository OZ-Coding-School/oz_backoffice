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
  permissions: [
    { code: "access.role.read", is_global: true, bootcamp_ids: [], cohort_ids: [] },
    { code: "access.role.manage", is_global: true, bootcamp_ids: [], cohort_ids: [] },
  ],
  cohorts: [],
};
const DEFS = [
  {
    code: "org.department.read",
    area: "조직",
    entity: "부서·팀",
    action: "조회",
    description: "부서·팀 조회",
    cohort_bound: false,
    requires: null,
  },
  {
    code: "org.department.manage",
    area: "조직",
    entity: "부서·팀",
    action: "관리",
    description: "부서·팀 추가·수정·삭제",
    cohort_bound: false,
    requires: "org.department.read",
  },
  {
    code: "mentoring.chat.read",
    area: "멘토링",
    entity: "채팅",
    action: "조회",
    description: "채팅 열람",
    cohort_bound: true,
    requires: null,
  },
];
const MANAGER = {
  id: "p1",
  name: "운영 매니저",
  priority: 2,
  assignment_scope: "COURSE",
  data_scope: "ASSIGNED",
  permissions: ["mentoring.chat.read"],
  employee_count: 6,
};

test("조직 설정 > 권한: 관리를 켜고 확인 후 저장 (FE-15d)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let saved: unknown = null;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/admin/permissions", (route) => route.fulfill({ json: DEFS }));
  await page.route("**/api/v1/admin/positions", (route) => route.fulfill({ json: [MANAGER] }));
  await page.route("**/api/v1/admin/positions/p1/permissions", async (route) => {
    saved = route.request().postDataJSON();
    return route.fulfill({ json: { ...MANAGER, permissions: (saved as { permissions: string[] }).permissions } });
  });

  await page.goto("/admin/org/permissions");
  const section = page.getByRole("region", { name: "운영 매니저 권한" });
  await expect(section.getByText("변경 사항 없음")).toBeVisible();
  await section.getByRole("checkbox", { name: "부서·팀 관리" }).click();
  await expect(section.getByRole("checkbox", { name: "부서·팀 조회" })).toBeChecked();
  await expect(section.getByText("저장하지 않은 변경 2개")).toBeVisible();
  await section.getByRole("button", { name: "저장" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "저장" }).click();
  await expect(section.getByText("변경 사항 없음")).toBeVisible();
  expect(saved).toEqual({ permissions: ["org.department.read", "org.department.manage", "mentoring.chat.read"] });
});
