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
  permissions: ["member.user.read", "member.user.manage"].map((code) => ({
    code,
    is_global: true,
    bootcamp_ids: [],
    cohort_ids: [],
  })),
  cohorts: [],
};
const KIM = {
  id: "u1",
  name: "김수강",
  email: "kim@gmail.com",
  phone_number: "01012341234",
  account_type: "STUDENT",
  is_active: true,
  is_super_admin: false,
  approved_at: "2025-11-03T01:00:00Z",
  last_login_at: null,
};
const DETAIL = {
  ...KIM,
  enrollments: [{ bootcamp_name: "백엔드 부트캠프", cohort_number: 12, status: "ENROLLED" }],
  assignments: [],
  contract_count: null,
  department_name: null,
  team_name: null,
  position_name: null,
  history: [],
};

test("회원 관리 > 전체 회원: 패널에서 사유를 적고 비활성화 (FE-15i)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let reason: unknown = null;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/admin/users?**", (route) =>
    route.fulfill({
      json: {
        items: [{ ...KIM, is_active: reason === null }],
        total: 1,
        limit: 20,
        offset: 0,
        counts: { ALL: 1, STUDENT: 1, MENTOR: 0, STAFF: 0 },
      },
    }),
  );
  await page.route("**/api/v1/admin/users/u1", (route) => route.fulfill({ json: DETAIL }));
  await page.route("**/api/v1/admin/users/u1/deactivate", (route) => {
    reason = route.request().postDataJSON();
    return route.fulfill({
      json: {
        ...DETAIL,
        is_active: false,
        history: [{ action: "DEACTIVATE", reason: "부정 사용", actor_name: "김관리", at: "2026-11-25T01:00:00Z" }],
      },
    });
  });

  await page.goto("/admin");
  await page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "회원" }).click();
  await page.getByRole("navigation", { name: "메뉴" }).getByRole("link", { name: "전체 회원" }).click();
  await page.getByRole("link", { name: "김수강" }).click();
  const sheet = page.getByRole("dialog", { name: "김수강" });
  await sheet.getByRole("button", { name: "비활성화" }).click();
  const dialog = page.getByRole("dialog", { name: "김수강 계정을 비활성화할까요?" });
  await dialog.getByRole("textbox", { name: "비활성화 사유" }).fill("부정 사용");
  await dialog.getByRole("button", { name: "비활성화" }).click();
  await expect(page.getByText("김수강 계정을 비활성화했어요")).toBeVisible();
  await expect(sheet.getByRole("list", { name: "이력" })).toContainText("부정 사용");
  expect(reason).toEqual({ reason: "부정 사용" });
});
