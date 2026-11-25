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
  permissions: ["academy.bootcamp.read", "academy.cohort.read", "academy.cohort.manage"].map((code) => ({
    code,
    is_global: true,
    bootcamp_ids: [],
    cohort_ids: [],
  })),
  cohorts: [],
};
const BE = {
  id: "b1",
  name: "백엔드 부트캠프",
  code: "BE",
  hrd_net_bootcamp_id: "h1",
  is_active: true,
  airtable_cohort_prefix: "백엔드",
  hrd_net_id: "AIG1",
  hrd_bootcamp_name: "백엔드 KDT",
};
const C12 = {
  id: "c12",
  bootcamp_id: "b1",
  hrd_net_cohort_id: "hc12",
  cohort_number: 12,
  start_date: "2026-06-02",
  end_date: "2026-11-30",
  status: "ONGOING",
  discord_guild_id: null,
  hrd_net_id: "AIG1",
  hrd_cohort_number: 12,
};
const SUMMARY = {
  students: { total: 2, linked: 1, by_status: { ENROLLED: 2 } },
  mentors: [],
  staff: [],
};

test("학사 > 과정·기수: 기수 패널에서 상태를 비활성으로 (FE-17a)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let body: unknown = null;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/admin/bootcamps?**", (route) => route.fulfill({ json: [BE] }));
  await page.route("**/api/v1/admin/bootcamps/b1/cohorts", (route) =>
    route.fulfill({ json: [{ ...C12, status: body ? "INACTIVE" : "ONGOING" }] }),
  );
  await page.route("**/api/v1/admin/cohorts/c12/summary", (route) => route.fulfill({ json: SUMMARY }));
  await page.route("**/api/v1/admin/cohorts/c12", (route) => {
    if (route.request().method() === "PATCH") {
      body = route.request().postDataJSON();
      return route.fulfill({ json: { ...C12, status: "INACTIVE" } });
    }
    return route.fulfill({ json: C12 });
  });

  await page.goto("/admin");
  await page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "학사" }).click();
  await expect(page.getByRole("table", { name: "기수" })).toBeVisible();
  await page.getByRole("link", { name: "12기" }).click();
  const sheet = page.getByRole("dialog", { name: "12기" });
  await expect(sheet.getByRole("region", { name: "수강생 2명" })).toBeVisible();
  await sheet.getByRole("button", { name: "수정" }).click();
  await sheet.getByRole("combobox", { name: "상태" }).click();
  await page.getByRole("option", { name: "비활성" }).click();
  await sheet.getByRole("button", { name: "저장" }).click();
  await expect(page.getByText("백엔드 부트캠프 12기를 저장했어요")).toBeVisible();
  expect(body).toEqual({ status: "INACTIVE" });
  await sheet.getByRole("button", { name: "닫기" }).click();
  await expect(page.getByRole("table", { name: "기수" })).toContainText("비활성");
});

test("학사 > HRD 과정: 회차 패널에서 자부담금 수정 (FE-17b)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const HRD = {
    id: "h1",
    name: "백엔드 KDT",
    hrd_net_id: "AIG1",
    train_type: "KDT",
    ncs1_se: null,
    ncs2_se: null,
    ncs3_se: null,
    weekend_se: "WEEKDAY",
    day_night_se: "DAY",
    total_train_fee: null,
    train_fee_per_hour: null,
    total_train_hours: null,
    total_train_days: null,
    bootcamps: [{ id: "b1", name: "백엔드 부트캠프", code: "BE" }],
    cohort_count: 1,
  };
  const ROUND = {
    id: "r15",
    hrd_net_bootcamp_id: "h1",
    cohort_number: 15,
    train_start_date: "2026-06-02",
    train_end_date: "2026-11-30",
    self_pay_amount: null,
    linked_cohorts: [],
  };
  let body: unknown = null;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) =>
    route.fulfill({
      json: {
        ...ACCESS,
        permissions: ["academy.hrd.read", "academy.hrd.manage"].map((code) => ({
          code,
          is_global: true,
          bootcamp_ids: [],
          cohort_ids: [],
        })),
      },
    }),
  );
  await page.route("**/api/v1/admin/hrd-bootcamps", (route) => route.fulfill({ json: [HRD] }));
  await page.route("**/api/v1/admin/hrd-bootcamps/h1/cohorts", (route) =>
    route.fulfill({ json: [{ ...ROUND, self_pay_amount: body ? 900000 : null }] }),
  );
  await page.route("**/api/v1/admin/hrd-cohorts/r15", (route) => {
    body = route.request().postDataJSON();
    return route.fulfill({ json: { ...ROUND, self_pay_amount: 900000 } });
  });

  await page.goto("/admin/academy/hrd");
  await page.getByRole("link", { name: "백엔드 KDT" }).click();
  await page
    .getByRole("dialog", { name: "백엔드 KDT" })
    .getByRole("link", { name: /15회차/ })
    .click();
  const sheet = page.getByRole("dialog", { name: "15회차" });
  await sheet.getByRole("button", { name: "수정" }).click();
  await sheet.getByRole("textbox", { name: "자부담금" }).fill("900000");
  await sheet.getByRole("button", { name: "저장" }).click();
  await expect(page.getByText("백엔드 KDT 15회차를 저장했어요")).toBeVisible();
  expect(body).toEqual({ self_pay_amount: 900000 });
  await expect(sheet).toContainText("900,000원");
});
