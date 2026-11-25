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
  permissions: ["org.position.read", "org.position.manage"].map((code) => ({
    code,
    is_global: true,
    bootcamp_ids: [],
    cohort_ids: [],
  })),
  cohorts: [],
};
const position = (id: string, name: string, priority: number) => ({
  id,
  name,
  priority,
  assignment_scope: "COURSE",
  data_scope: "ASSIGNED",
  permissions: [],
  employee_count: 0,
});
const POSITIONS = [position("p1", "팀리드", 10), position("p2", "운영 매니저", 20), position("p3", "조교", 30)];

test("조직 설정 > 직위: 끌어서 순서를 바꾸고 저장 (FE-15h)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const patched: { id: string; body: unknown }[] = [];
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/admin/positions", (route) => route.fulfill({ json: POSITIONS }));
  await page.route("**/api/v1/admin/positions/*", (route) => {
    const id = new URL(route.request().url()).pathname.split("/").pop() ?? "";
    patched.push({ id, body: route.request().postDataJSON() });
    return route.fulfill({ json: { ...POSITIONS.find((p) => p.id === id), ...route.request().postDataJSON() } });
  });

  await page.goto("/admin");
  await page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "조직" }).click();
  await page.getByRole("navigation", { name: "메뉴" }).getByRole("link", { name: "직위" }).click();
  const table = page.getByRole("table", { name: "직위" });
  await table.getByRole("button", { name: /조교 순서 옮기기/ }).dragTo(table.getByRole("row", { name: "팀리드" }));
  await expect(page.getByText("순서가 바뀌었어요")).toBeVisible();
  await page.getByRole("button", { name: "순서 저장" }).click();
  await expect(page.getByText("직위 순서를 저장했어요")).toBeVisible();
  expect(patched).toEqual([
    { id: "p3", body: { priority: 10 } },
    { id: "p1", body: { priority: 20 } },
    { id: "p2", body: { priority: 30 } },
  ]);
});
