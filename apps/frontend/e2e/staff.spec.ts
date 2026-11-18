import { expect, test } from "@playwright/test";

test("운영진 로그인: Google 실패 안내를 보여 주고, 버튼은 백엔드 Google 로그인으로 보낸다", async ({ page }) => {
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ status: 401, json: { error: { code: "refresh_token_missing", message: "" } } }),
  );
  let googleLogin = false;
  await page.route("**/api/v1/auth/google/login", (route) => {
    googleLogin = true;
    return route.fulfill({ status: 200, contentType: "text/html", body: "<p>google</p>" });
  });
  await page.goto("/staff/login?error=google_domain_not_allowed");
  await expect(page.getByRole("alert")).toContainText("회사 Google 계정으로만 로그인할 수 있어요");
  await page.getByRole("button", { name: "Google 계정으로 로그인" }).click();
  await expect.poll(() => googleLogin).toBe(true);
});
