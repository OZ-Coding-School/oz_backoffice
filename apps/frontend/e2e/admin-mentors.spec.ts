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
  permissions: ["educator.mentor.read", "educator.mentor.manage"].map((code) => ({
    code,
    is_global: true,
    bootcamp_ids: [],
    cohort_ids: [],
  })),
  cohorts: [],
};
const KIM = {
  id: "m1",
  user_id: "u1",
  name: "김멘토",
  email: "kim@mentor.com",
  phone_number: "01011111234",
  display_name: "멘토K",
  is_active: true,
  contract_count: 2,
  created_at: "2026-11-03T01:00:00Z",
  accepting_requests: true,
  active_cohorts: [{ cohort_id: "c12", bootcamp_name: "백엔드", cohort_number: 12 }],
};
const PROFILE = {
  id: "m1",
  user_id: "u1",
  name: "김멘토",
  display_name: "멘토K",
  nickname: "멘토K",
  display_name_preference: "NICKNAME",
  headline: "백엔드 7년 차",
  introduction: "## 이런 분께 추천해요\n- 첫 포트폴리오",
  expertise: "백엔드",
  profile_image_url: null,
  is_active: true,
};

test("강사·멘토 > 멘토: 목록에서 상세로, 소개를 마크다운으로 고친다 (FE-18a)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let profile = { ...PROFILE };
  let saved: Record<string, unknown> | null = null;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: ADMIN }));
  await page.route("**/api/v1/me/staff-access", (route) => route.fulfill({ json: ACCESS }));
  await page.route("**/api/v1/admin/mentors?**", (route) =>
    route.fulfill({ json: { items: [KIM], total: 1, limit: 20, offset: 0 } }),
  );
  await page.route("**/api/v1/admin/mentors/m1", (route) => route.fulfill({ json: KIM }));
  await page.route("**/api/v1/admin/mentors/m1/profile", (route) => {
    if (route.request().method() === "PATCH") {
      saved = route.request().postDataJSON() as Record<string, unknown>;
      profile = { ...profile, ...saved };
    }
    return route.fulfill({ json: profile });
  });

  await page.goto("/admin");
  await page.getByRole("navigation", { name: "모듈" }).getByRole("link", { name: "강사·멘토" }).click();
  await page.getByRole("table", { name: "멘토" }).getByRole("link", { name: "김멘토(멘토K)" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "김멘토" })).toBeVisible();
  await page.getByRole("button", { name: "프로필 수정" }).click();
  const form = page.getByRole("form", { name: "프로필 수정" });
  await form.getByRole("textbox", { name: "소개 (마크다운)" }).fill("## 경력\n커머스 서버 5년");
  await expect(
    page.getByRole("region", { name: "수강생에게 보이는 모습" }).getByRole("heading", { name: "경력" }),
  ).toBeVisible();
  await form.getByRole("button", { name: "저장" }).click();
  await expect(page.getByText("프로필을 저장했어요")).toBeVisible();
  expect(saved).toMatchObject({ introduction: "## 경력\n커머스 서버 5년" });
  await expect(
    page.getByRole("region", { name: "수강생에게 보이는 모습" }).getByRole("heading", { name: "경력" }),
  ).toBeVisible();
});
