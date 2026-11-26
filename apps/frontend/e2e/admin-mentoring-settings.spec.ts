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
  cohorts: [
    {
      id: "c12",
      bootcamp_id: "b1",
      bootcamp_name: "백엔드 부트캠프",
      cohort_number: 12,
      start_date: "2026-09-01",
      end_date: "2027-02-28",
      status: "ONGOING",
    },
  ],
};

test("멘토링 > 멘토링 설정: 메뉴로 현재 기수 설정에 들어가 처음 저장한다 (FE-19a)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let saved: Record<string, unknown> | null = null;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/admin/cohorts/c12/mentoring-block-times", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/admin/cohorts/c12/mentoring-settings", async (route) => {
    if (route.request().method() === "PUT") {
      saved = route.request().postDataJSON() as Record<string, unknown>;
      return route.fulfill({ json: { ...saved, cohort_id: "c12", updated_at: "2026-11-26T05:00:00Z" } });
    }
    return route.fulfill({
      status: 404,
      json: { error: { code: "mentoring_settings_not_configured", message: "없음", details: null } },
    });
  });

  await page.goto("/admin");
  await page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "멘토링" }).click();
  await expect(page).toHaveURL(/\/admin\/cohorts\/c12\/mentoring\/settings$/);
  await expect(page.getByRole("button", { name: "현재 기수" })).toContainText("백엔드 부트캠프 12기");
  await expect(page.getByText("아직 저장하지 않은 기수예요")).toBeVisible();
  await page.getByRole("radio", { name: "60분" }).click();
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page.getByText("멘토링 설정을 저장했어요")).toBeVisible();
  expect(saved).toMatchObject({ allowed_duration: 60, allow_1_on_1: true });
});
