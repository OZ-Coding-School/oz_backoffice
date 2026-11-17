import { expect, test, type Page } from "@playwright/test";

const ME = {
  id: "u1",
  email: "student@gmail.com",
  name: "가수강",
  account_type: "MEMBER",
  phone_number: "01012345678",
  approval_status: "APPROVED",
  approved_at: "2026-11-16T01:00:00Z",
  roles: [{ role: "STUDENT", scope_type: "COHORT", scope_id: "c1", expires_at: null }],
};

async function mockAuth(page: Page) {
  let signedIn = false;
  await page.route("**/api/v1/auth/refresh", (route) =>
    signedIn
      ? route.fulfill({ json: { access_token: "t2", expires_at: new Date(Date.now() + 900_000).toISOString() } })
      : route.fulfill({ status: 401, json: { error: { code: "refresh_token_missing", message: "" } } }),
  );
  await page.route("**/api/v1/auth/login", async (route) => {
    const body = route.request().postDataJSON() as { password: string };
    if (body.password !== "secret1!") {
      return route.fulfill({ status: 401, json: { error: { code: "invalid_credentials", message: "" } } });
    }
    signedIn = true;
    return route.fulfill({ json: { access_token: "t1", expires_at: new Date(Date.now() + 900_000).toISOString() } });
  });
  await page.route("**/api/v1/auth/logout", (route) => {
    signedIn = false;
    return route.fulfill({ status: 204 });
  });
  await page.route("**/api/v1/me", (route) =>
    route.request().headers()["authorization"]
      ? route.fulfill({ json: ME })
      : route.fulfill({ status: 401, json: { error: { code: "unauthenticated", message: "" } } }),
  );
}

test("로그인하고, 새로고침해도 세션이 유지되고, 로그아웃한다", async ({ page }) => {
  await mockAuth(page);
  await page.goto("/");
  await page.getByLabel("이메일").fill("student@gmail.com");
  await page.getByLabel("비밀번호", { exact: true }).fill("wrong");
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page.getByRole("alert")).toContainText("이메일 또는 비밀번호가 올바르지 않아요");

  await page.getByLabel("비밀번호", { exact: true }).fill("secret1!");
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page.getByRole("heading", { name: "안녕하세요, 가수강님" })).toBeVisible();
  await expect(page).toHaveURL(/\/$/);

  await page.reload();
  await expect(page.getByRole("heading", { name: "안녕하세요, 가수강님" })).toBeVisible();

  await page.getByRole("button", { name: "로그아웃" }).click();
  await expect(page.getByRole("heading", { name: "로그인" })).toBeVisible();
});

test("모바일에서는 소개 영역을 숨기고 로고를 위에 둔다", async ({ page }) => {
  await mockAuth(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");
  await expect(page.getByRole("complementary")).toBeHidden();
  await expect(page.getByRole("main").getByText("오즈코딩스쿨 운영 행정 지원 플랫폼")).toBeVisible();

  await page.setViewportSize({ width: 768, height: 1024 });
  await expect(page.getByRole("complementary")).toBeVisible();
  await expect(page.getByRole("complementary")).toHaveCSS("width", "320px");
});
