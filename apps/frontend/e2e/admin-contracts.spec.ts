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
const base = {
  contract_type: "SW",
  bootcamp_id: "b1",
  bootcamp_name: "백엔드 부트캠프",
  cohort_id: null,
  cohort_number: null,
  business_registration_number: null,
  contact_person_name: null,
  settlement_type: "FIXED",
  total_amount: null,
  unit_price: null,
  price_unit: null,
  vat_type: "NOT_APPLICABLE",
  amount_note: null,
  no_show_pay_amount: null,
  mentoring_time_basis: null,
  cancel_reason: null,
  canceled_on: null,
  termination_reason: null,
  termination_detail: null,
  terminated_on: null,
  contractor_phone: null,
  contractor_email: null,
  manager_employee_id: "e1",
  manager_name: "김관리",
  mentor_id: null,
  instructor_id: null,
  linked_profile: null,
  contract_file: null,
  start_date: null,
  end_date: null,
  created_at: "2026-11-25T01:00:00Z",
  updated_at: null,
};

test("행정 업무 > 계약: 위저드로 과정 공통 SW 계약을 초안으로 만들고 패널에서 상태 단계를 본다 (F96)", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const contracts: Record<string, unknown>[] = [];
  let created: Record<string, unknown> | null = null;
  let listQuery = "";
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
  await page.route("**/api/v1/admin/contracts/k9/amendments", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/admin/contracts/k9", (route) => route.fulfill({ json: contracts[0] }));
  await page.route("**/api/v1/admin/contracts?**", (route) => {
    listQuery = new URL(route.request().url()).search;
    return route.fulfill({
      json: {
        items: contracts,
        total: contracts.length,
        limit: 20,
        offset: 0,
        counts: { MENTOR: 0, INSTRUCTOR: 0, SW: contracts.length, EQUIPMENT: 0, OTHER: 0 },
      },
    });
  });
  await page.route("**/api/v1/admin/contracts", (route) => {
    created = route.request().postDataJSON() as Record<string, unknown>;
    const saved = { ...base, ...created, id: "k9", status: "DRAFT" };
    contracts.unshift(saved);
    return route.fulfill({ status: 201, json: saved });
  });

  await page.goto("/admin");
  await page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "행정 업무" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "계약" })).toBeVisible();
  await expect(page.getByRole("button", { name: "과정 / 기수" })).toContainText("백엔드 부트캠프 12기");
  expect(listQuery).toContain("include_bootcamp_common=true");
  await page.getByRole("button", { name: "계약 추가" }).click();
  const sheet = page.getByRole("dialog", { name: "계약 추가" });
  await sheet.getByRole("radio", { name: "SW" }).click();
  await sheet.getByRole("combobox", { name: "기수" }).click();
  await page.getByRole("option", { name: "과정 공통" }).click();
  await sheet.getByRole("textbox", { name: "계약 명칭" }).fill("백엔드 과정 Zoom 라이선스");
  await sheet.getByRole("button", { name: /다음/ }).click();
  await sheet.getByRole("textbox", { name: "업체명" }).fill("줌코리아");
  await sheet.getByRole("button", { name: /다음/ }).click();
  await sheet.getByRole("radio", { name: "정액" }).click();
  await sheet.getByRole("textbox", { name: "계약 금액" }).fill("1200000");
  await expect(sheet.getByRole("textbox", { name: "계약 금액" })).toHaveValue("1,200,000");
  await sheet.getByRole("button", { name: /다음/ }).click();
  await sheet.getByRole("button", { name: /다음/ }).click();
  await expect(sheet.getByRole("region", { name: "확인" })).toContainText("정액 1,200,000원");
  await sheet.getByRole("button", { name: "초안으로 저장" }).click();
  await expect(page.getByText("계약을 초안으로 저장했어요")).toBeVisible();
  expect(created).toMatchObject({
    contract_type: "SW",
    bootcamp_id: "b1",
    cohort_id: null,
    contractor_name: "줌코리아",
    settlement_type: "FIXED",
    total_amount: 1_200_000,
    manager_employee_id: "e1",
  });
  const panel = page.getByRole("dialog", { name: "백엔드 과정 Zoom 라이선스" });
  await expect(panel.getByRole("list", { name: "계약 단계" })).toBeVisible();
  await expect(panel.getByRole("button", { name: "진행" })).toBeVisible();
  await panel.getByRole("button", { name: "닫기" }).click();
  await expect(page.getByRole("table", { name: "계약" })).toContainText("백엔드 부트캠프 / 공통");
});
