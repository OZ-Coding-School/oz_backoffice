import { expect, test } from "@playwright/test";

test("로그인하지 않고 홈에 오면 로그인 화면이 뜬다", async ({ page }) => {
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ status: 401, json: { error: { code: "refresh_token_missing", message: "" } } }),
  );
  await page.goto("/");
  await expect(page).toHaveTitle("오즈코딩스쿨 운영 행정 지원 플랫폼");
  await expect(page.getByRole("heading", { level: 1, name: "로그인" })).toBeVisible();
  await expect(page).toHaveURL(/\/login\?redirect=%2F$/);
});
