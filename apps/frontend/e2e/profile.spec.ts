import { expect, test, type Page } from "@playwright/test";

const ME = {
  id: "u1",
  email: "student@gmail.com",
  name: "가수강",
  account_type: "STUDENT",
  phone_number: "01012345678",
  approval_status: "APPROVED",
  approved_at: "2026-11-16T01:00:00Z",
  roles: [{ role: "STUDENT", scope_type: "COHORT", scope_id: "c12", expires_at: null }],
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
async function mockApi(page: Page) {
  let state: "NONE" | "SENT" | "VERIFIED" = "NONE";
  let polls = 0;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ME }));
  await page.route("**/api/v1/me/enrollments", (route) => route.fulfill({ json: [ENROLLMENT] }));
  await page.route("**/api/v1/me/password-change", (route) => {
    if (route.request().method() === "POST") {
      state = "NONE";
      return route.fulfill({ status: 204, body: "" });
    }
    // 링크를 보낸 뒤 두 번째 확인에서 인증된다
    if (state === "SENT" && ++polls >= 2) state = "VERIFIED";
    const minutes = state === "VERIFIED" ? 10 : 30;
    return route.fulfill({
      json: {
        available: true,
        state,
        expires_at: state === "NONE" ? null : new Date(Date.now() + minutes * 60_000).toISOString(),
      },
    });
  });
  await page.route("**/api/v1/me/password-change/link", (route) => {
    state = "SENT";
    return route.fulfill({
      json: { available: true, state, expires_at: new Date(Date.now() + 30 * 60_000).toISOString() },
    });
  });
}

test("휴대폰: 더보기 → 내 정보 → 링크 인증 후 비밀번호 변경 (F37·A72)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockApi(page);
  await page.goto("/");
  // 채팅이 생겨 메뉴가 6개라 내 정보는 더보기 안에 있다 (F36·F40)
  await page.getByRole("navigation", { name: "하단 메뉴" }).getByRole("button", { name: "더보기" }).click();
  await page.getByRole("dialog", { name: "더보기" }).getByRole("link", { name: "내 정보" }).click();
  await expect(page.getByRole("heading", { name: "내 정보" })).toBeVisible();
  await expect(page.getByText("010-****-5678")).toBeVisible();

  await page.getByRole("button", { name: "비밀번호 재설정" }).click();
  const dialog = page.getByRole("dialog", { name: "비밀번호 변경" });
  await expect(dialog.getByText("st****@gmail.com으로 인증 링크를 보냈어요")).toBeVisible();
  await expect(dialog.getByText("이메일 인증이 완료되었습니다.")).toBeVisible({ timeout: 15_000 });

  await dialog.getByLabel("새 비밀번호", { exact: true }).fill("newpass1!");
  await dialog.getByLabel("새 비밀번호 확인").fill("newpass1!");
  await expect(dialog.getByText("비밀번호가 일치해요")).toBeVisible();
  await dialog.getByRole("button", { name: "변경 저장" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByText("비밀번호를 바꿨어요")).toBeVisible();
});

test("메일 링크를 열면 인증 완료를 알려 준다 (A72)", async ({ page }) => {
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ status: 401, json: { error: { code: "refresh_token_missing", message: "x" } } }),
  );
  await page.route("**/api/v1/auth/password-change/verify", (route) => route.fulfill({ status: 204, body: "" }));
  await page.goto("/password-change/verify?token=abc");
  await expect(page.getByRole("heading", { name: "이메일 인증이 완료되었습니다." })).toBeVisible();
});
