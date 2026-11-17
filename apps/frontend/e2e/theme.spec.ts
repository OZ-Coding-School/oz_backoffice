import { expect, test } from "@playwright/test";

test.describe("디자인 토큰", () => {
  test("시스템이 다크면 첫 화면부터 다크 테마를 적용한다", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/");
    await expect(page.locator("html")).toHaveClass(/dark/);
    // Figma Color/Dark base/background (zinc 850)
    await expect(page.locator("body")).toHaveCSS("background-color", "rgb(31, 31, 35)");
  });

  test("고른 테마를 기억한다", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.addInitScript({ content: 'localStorage.setItem("oz-theme", "light")' });
    await page.goto("/");
    await expect(page.locator("html")).not.toHaveClass(/dark/);
    await expect(page.locator("body")).toHaveCSS("background-color", "rgb(255, 255, 255)");
  });

  test("본문 글꼴은 앱에 포함한 Noto Sans KR이다", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("body")).toHaveCSS("font-family", /Noto Sans KR Variable/);
    // 한글 글자의 글꼴 파일까지 실제로 받았는지 확인한다
    await page.evaluate('document.fonts.load(\'16px "Noto Sans KR Variable"\', "가")');
    expect(await page.evaluate('document.fonts.check(\'16px "Noto Sans KR Variable"\', "가")')).toBe(true);
  });

  test("확인용 화면은 운영 빌드에 없다", async ({ page }) => {
    await page.goto("/dev/design-system");
    await expect(page.getByRole("heading", { name: "페이지를 찾을 수 없습니다" })).toBeVisible();
  });
});
