import { expect, test } from "@playwright/test";

const STAFF = {
  id: "u1",
  email: "staff@nextrunners.co.kr",
  name: "김운영",
  account_type: "STAFF",
  phone_number: null,
  approval_status: "APPROVED",
  approved_at: "2026-11-01T01:00:00Z",
  is_super_admin: false,
};
const ACCESS = {
  is_super_admin: false,
  position: { id: "p1", name: "운영 매니저", all_data: false },
  permissions: [{ code: "member.approval.read", is_global: false, bootcamp_ids: [], cohort_ids: ["c12"] }],
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

test("운영진 틀: 모듈 레일·메뉴와 사용자 메뉴의 역할 (FE-14a)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: STAFF }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));

  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "안녕하세요, 김운영님" })).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "홈", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "사용자 메뉴" }).click();
  await expect(page.getByRole("menu")).toContainText("운영 매니저 · 담당 과정·기수");
});
