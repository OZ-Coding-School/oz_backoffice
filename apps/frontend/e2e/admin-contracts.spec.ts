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
  permissions: ["educator.contract.read", "educator.contract.manage", "educator.mentor.read"].map((code) => ({
    code,
    is_global: true,
    bootcamp_ids: [],
    cohort_ids: [],
  })),
  cohorts: [],
};
const base = {
  contract_type: "MENTOR",
  bootcamp_id: "b1",
  bootcamp_name: "백엔드 부트캠프",
  cohort_id: "c12",
  cohort_number: 12,
  business_registration_number: null,
  contact_person_name: null,
  settlement_type: "UNIT_PRICE",
  total_amount: null,
  unit_price: 50000,
  price_unit: "HOURLY",
  vat_type: "NOT_APPLICABLE",
  amount_note: null,
  no_show_pay_amount: 0,
  mentoring_time_basis: "ACTUAL_DURATION",
  cancel_reason: null,
  canceled_on: null,
  termination_reason: null,
  termination_detail: null,
  terminated_on: null,
  contractor_email: null,
  manager_employee_id: "e1",
  manager_name: "김관리",
  instructor_id: null,
  contract_file: null,
  created_at: "2026-11-25T01:00:00Z",
  updated_at: null,
};

test("행정 업무 > 계약: 멘토 계약을 추가하고 패널에서 확정 버튼을 본다 (FE-18b)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const contracts: Record<string, unknown>[] = [];
  let created: Record<string, unknown> | null = null;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/admin/contracts/manager-candidates**", (route) =>
    route.fulfill({
      json: [
        {
          employee_id: "e1",
          name: "김관리",
          email: "boss@nextrunners.co.kr",
          department_name: "운영",
          team_name: "운영팀",
          position_name: "팀장",
          is_me: true,
        },
      ],
    }),
  );
  await page.route("**/api/v1/admin/contracts/k9", (route) => route.fulfill({ json: contracts[0] }));
  await page.route("**/api/v1/admin/contracts?**", (route) =>
    route.fulfill({ json: { items: contracts, total: contracts.length, limit: 20, offset: 0 } }),
  );
  await page.route("**/api/v1/admin/contracts", (route) => {
    created = route.request().postDataJSON() as Record<string, unknown>;
    const saved = {
      ...base,
      ...created,
      id: "k9",
      status: "DRAFT",
      mentor_id: "m9",
      linked_profile: { name: "이멘토", display_name: "이멘토" },
    };
    contracts.unshift(saved);
    return route.fulfill({ status: 201, json: saved });
  });

  await page.goto("/admin");
  await page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "행정 업무" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "계약" })).toBeVisible();
  await page.getByRole("button", { name: "계약 추가" }).click();
  const form = page.getByRole("form", { name: "계약 추가" });
  await form.getByLabel("계약자").fill("이멘토");
  await form.getByLabel("휴대폰").fill("010-2222-5678");
  await form.getByLabel("제목").fill("2026 데이터 멘토 계약");
  await form.getByLabel("시작일").fill("2026-12-01");
  await form.getByLabel("종료일").fill("2027-05-31");
  await expect(form.getByRole("option", { name: /김관리 \(나\)/ })).toHaveAttribute("aria-selected", "true");
  await form.getByRole("button", { name: "추가" }).click();
  await expect(page.getByText("계약을 작성 중으로 저장했어요")).toBeVisible();
  expect(created).toMatchObject({ contractor_name: "이멘토", manager_employee_id: "e1", contract_type: "MENTOR" });
  const sheet = page.getByRole("dialog", { name: "2026 데이터 멘토 계약" });
  await expect(sheet.getByRole("button", { name: "확정" })).toBeVisible();
});
