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
  permissions: ["mentoring.settings.read", "mentoring.settings.manage"].map((code) => ({
    code,
    is_global: true,
    bootcamp_ids: [],
    cohort_ids: [],
  })),
  cohorts: [],
};

test("설정 > 공휴일: 평일을 눌러 추가 휴일로 등록 (FE-16)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const items = [{ id: null, holiday_date: "2026-08-15", name: "광복절", source: "PUBLIC" }];
  let created: unknown = null;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/admin/mentoring-holidays?**", (route) =>
    route.fulfill({ json: { items, synced_at: "2026-11-24T18:00:00Z" } }),
  );
  await page.route("**/api/v1/admin/mentoring-holidays", (route) => {
    created = route.request().postDataJSON();
    items.push({ id: "c1", holiday_date: "2026-06-05", name: "임시 휴무", source: "CUSTOM" } as never);
    return route.fulfill({ status: 201, json: items.at(-1) });
  });

  await page.goto("/admin");
  await page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "설정" }).click();
  await page.goto("/admin/settings/holidays?year=2026");
  await expect(page.getByRole("region", { name: "12월" })).toBeVisible();
  await page.getByRole("region", { name: "6월" }).getByRole("link", { name: "6월 5일", exact: true }).click();
  const panel = page.getByRole("region", { name: "선택한 날" });
  await expect(panel).toContainText("2026년 6월 5일 (금)");
  await panel.getByRole("textbox", { name: "휴일 이름" }).fill("임시 휴무");
  await panel.getByRole("button", { name: "추가 휴일로 등록" }).click();
  await expect(page.getByText("6/5 (금) 임시 휴무를 추가 휴일로 등록했어요")).toBeVisible();
  expect(created).toEqual({ holiday_date: "2026-06-05", name: "임시 휴무" });
  await expect(panel).toContainText("구분추가 휴일");
});
