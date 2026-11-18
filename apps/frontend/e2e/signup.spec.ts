import { expect, test } from "@playwright/test";

test("휴대폰 화면에서 회원가입을 마치고 로그인 화면으로 간다", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ status: 401, json: { error: { code: "refresh_token_missing", message: "" } } }),
  );
  await page.route("**/api/v1/auth/signup/email-code", (route) => route.fulfill({ status: 204 }));
  await page.route("**/api/v1/auth/signup/email-code/verify", (route) =>
    route.fulfill({ json: { signup_token: "t", expires_in: 1800 } }),
  );
  await page.route("**/api/v1/auth/signup/phone-code", (route) => route.fulfill({ status: 204 }));
  await page.route("**/api/v1/auth/signup/phone-code/verify", (route) => route.fulfill({ status: 204 }));
  await page.route("**/api/v1/auth/signup/cohorts", (route) =>
    route.fulfill({
      json: [
        {
          cohort_id: "c12",
          bootcamp_id: "b1",
          bootcamp_name: "백엔드",
          cohort_number: 12,
          start_date: "2026-11-01",
          end_date: "2027-04-30",
        },
      ],
    }),
  );
  await page.route("**/api/v1/auth/signup", (route) =>
    route.fulfill({
      status: 201,
      json: { user_id: "u1", signup_id: "s1", signup_type: "STUDENT", approval_status: "PENDING" },
    }),
  );

  await page.goto("/login");
  await page.getByRole("link", { name: "수강생·멘토 가입" }).click();
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByLabel("이메일").fill("student@gmail.com");
  await page.getByRole("button", { name: "인증코드 받기" }).click();
  await page.getByLabel("인증코드").fill("123456");
  await page.getByRole("button", { name: "확인" }).click();
  await page.getByLabel("휴대폰 번호").pressSequentially("01012345678");
  await expect(page.getByLabel("휴대폰 번호")).toHaveValue("010-1234-5678");
  await page.getByRole("button", { name: "인증코드 받기" }).click();
  await page.getByLabel("인증코드").fill("654321");
  await page.getByRole("button", { name: "확인" }).click();

  await page.getByLabel("이름").fill("가수강");
  await page.getByRole("combobox", { name: "신청 기수" }).click();
  await page.getByRole("option", { name: /백엔드 12기/ }).click();
  await page.getByLabel("비밀번호", { exact: true }).fill("secret12!");
  await page.getByLabel("비밀번호 확인").fill("secret12!");
  await page.getByRole("button", { name: "가입 신청" }).click();

  await expect(page.getByRole("heading", { name: "가입 신청을 받았어요" })).toBeVisible();
  await page.getByRole("link", { name: "로그인하기" }).click();
  await expect(page.getByLabel("이메일")).toHaveValue("student@gmail.com");
});
