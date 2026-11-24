import { expect, test, type Page } from "@playwright/test";

const ME = {
  id: "u1",
  email: "student@gmail.com",
  name: "가수강",
  account_type: "STUDENT",
  phone_number: "01012345678",
  approval_status: "APPROVED",
  approved_at: "2026-11-16T01:00:00Z",
  is_super_admin: false,
};
const ENROLLMENT = {
  student_id: "st12",
  cohort_id: "c12",
  bootcamp_id: "b1",
  bootcamp_name: "초격차 백엔드",
  cohort_number: 12,
  cohort_status: "ONGOING",
  start_date: "2026-10-01",
  end_date: "2027-03-31",
  status: "ENROLLED",
  enrolled_at: "2026-10-01",
  ended_at: null,
};

async function signedIn(page: Page) {
  let active = true;
  await page.route("**/api/v1/auth/refresh", (route) =>
    active
      ? route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } })
      : route.fulfill({ status: 401, json: { error: { code: "refresh_token_missing", message: "" } } }),
  );
  await page.route("**/api/v1/auth/logout", (route) => {
    active = false;
    return route.fulfill({ status: 204 });
  });
  await page.route("**/api/v1/me/enrollments", (route) => route.fulfill({ json: [ENROLLMENT] }));
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ME }));
}

test("휴대폰: 사이드바·레일 없이 상단 막대만, 사용자 메뉴에서 로그아웃 (F27)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signedIn(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "안녕하세요, 가수강님" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "메뉴", exact: true })).toHaveCount(0); // 사이드바·레일은 숨김
  await expect(page.getByRole("navigation", { name: "하단 메뉴" })).toBeVisible(); // 메뉴 2개(홈·신청 내역)
  await page.getByRole("button", { name: "사용자 메뉴" }).click();
  await expect(page.getByRole("menu").getByText("수강생 · 초격차 백엔드 12기")).toBeVisible();
  await page.getByRole("menuitem", { name: "로그아웃" }).click();
  await expect(page.getByRole("heading", { name: "로그인" })).toBeVisible();
});

test("태블릿: 레일에 아이콘과 짧은 이름 (F27)", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  await signedIn(page);
  await page.goto("/");
  const rail = page.getByRole("navigation", { name: "메뉴", exact: true }); // 사이드바는 숨기고 레일만 보인다
  await expect(rail).toBeVisible();
  await expect(rail.getByRole("link", { name: "홈" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("button", { name: "사용자 메뉴" })).toBeVisible();
});
