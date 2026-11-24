import { deflateSync } from "node:zlib";

import { expect, test, type Page } from "@playwright/test";

const MENTOR = {
  id: "u9",
  email: "mentor@gmail.com",
  name: "김멘토",
  account_type: "MENTOR",
  phone_number: "01012345678",
  approval_status: "APPROVED",
  approved_at: "2026-11-01T01:00:00Z",
  is_super_admin: false,
};
const PROFILE = {
  id: "m1",
  user_id: "u9",
  name: "김멘토",
  display_name: "김멘토",
  nickname: null,
  display_name_preference: "NAME",
  headline: "백엔드 7년차",
  introduction: null,
  expertise: "Python",
  profile_image_url: null,
  is_active: true,
};

/** 가로로 긴 RGB PNG (가운데 정사각형으로 잘리는지 보려고) */
function png(width: number, height: number): Buffer {
  const table = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf: Buffer) => {
    let x = 0xffffffff;
    for (const b of buf) x = table[(x ^ b) & 0xff]! ^ (x >>> 8);
    return (x ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type), data]);
    const sum = Buffer.alloc(4);
    sum.writeUInt32BE(crc(body));
    return Buffer.concat([len, body, sum]);
  };
  const raw = Buffer.alloc((width * 3 + 1) * height, 128);
  for (let y = 0; y < height; y++) raw[y * (width * 3 + 1)] = 0;
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 2;
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

async function mockMentor(page: Page) {
  let profile: Record<string, unknown> = { ...PROFILE };
  const uploaded: { type: string | undefined; size: number }[] = [];
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill({ json: { access_token: "t", expires_at: new Date(Date.now() + 900_000).toISOString() } }),
  );
  await page.route("**/api/v1/me", (route) => route.fulfill({ json: MENTOR }));
  await page.route("**/api/v1/me/mentoring/chat/threads**", (route) =>
    route.fulfill({ json: { items: [], total: 0, limit: 50, offset: 0 } }),
  );
  await page.route("**/api/v1/me/mentoring/chat/stream", (route) =>
    route.fulfill({ headers: { "Content-Type": "text/event-stream" }, body: "event: ready\ndata: {}\n\n" }),
  );
  await page.route("**/api/v1/me/mentor-requests**", (route) =>
    route.fulfill({
      json: { items: [], total: 0, limit: 1, offset: 0, counts: { PENDING: 0, APPROVED: 0, REJECTED: 0, CANCELED: 0 } },
    }),
  );
  await page.route("**/api/v1/me/mentor-sessions**", (route) =>
    route.fulfill({
      json: {
        items: [],
        total: 0,
        limit: 20,
        offset: 0,
        counts: { SCHEDULED: 0, IN_PROGRESS: 0, COMPLETED: 0, NO_SHOW: 0, CANCELED: 0 },
        view_counts: { upcoming: 0, record_missing: 0, past: 0, all: 0 },
      },
    }),
  );
  await page.route("**/api/v1/me/mentor-assignments**", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/me/password-change", (route) =>
    route.fulfill({ json: { available: true, state: "NONE", expires_at: null } }),
  );
  await page.route("**/api/v1/me/mentor-profile", async (route) => {
    if (route.request().method() === "PATCH") profile = { ...profile, ...route.request().postDataJSON() };
    return route.fulfill({ json: profile });
  });
  await page.route("**/api/v1/me/mentor-profile/image/uploads", (route) =>
    route.fulfill({
      json: {
        upload_id: "up1",
        url: "http://localhost:4173/__s3",
        fields: { key: "mentors/m1/up1" },
        expires_at: new Date(Date.now() + 600_000).toISOString(),
        max_bytes: 2097152,
      },
    }),
  );
  await page.route("**/__s3", (route) => {
    const body = route.request().postDataBuffer() ?? Buffer.alloc(0);
    const text = body.toString("latin1");
    uploaded.push({ type: /Content-Type: (image\/\w+)/.exec(text)?.[1], size: body.length });
    return route.fulfill({ status: 204 });
  });
  await page.route("**/api/v1/me/mentor-profile/image/uploads/up1/confirm", (route) => {
    profile = { ...profile, profile_image_url: "data:image/gif;base64,R0lGODlhAQABAAAAACw=" };
    return route.fulfill({ json: profile });
  });
  return uploaded;
}

test.describe("멘토 내 프로필", () => {
  test("데스크톱: 메뉴 → 내 프로필 → 사진을 WebP로 줄여 한 줄 소개와 함께 저장 (F56)", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const uploaded = await mockMentor(page);

    await page.goto("/");
    await page.getByRole("navigation", { name: "메뉴", exact: true }).getByRole("link", { name: "내 프로필" }).click();
    await expect(page.getByRole("heading", { name: "내 프로필", level: 1 })).toBeVisible();
    await page.getByLabel("프로필 사진 고르기").setInputFiles({
      name: "wide.png",
      mimeType: "image/png",
      buffer: png(900, 600),
    });
    // 가운데를 잘라 512×512로 줄였다
    const preview = page.getByRole("img", { name: "프로필 사진" });
    await expect(preview).toHaveJSProperty("naturalWidth", 512);
    await expect(preview).toHaveJSProperty("naturalHeight", 512);
    await page.getByRole("textbox", { name: "한 줄 소개" }).fill("포트폴리오 리뷰");
    await page.getByRole("button", { name: "저장" }).click();
    await expect(page.getByText("프로필을 저장했어요")).toBeVisible();
    expect(uploaded).toHaveLength(1);
    expect(uploaded[0]?.type).toBe("image/webp");
    await expect(page.getByRole("button", { name: "저장" })).toBeDisabled();
  });

  test("휴대폰: 더보기 → 내 프로필, 저장하지 않고 떠나면 확인 (F56)", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockMentor(page);

    await page.goto("/");
    const tabs = page.getByRole("navigation", { name: "하단 메뉴" });
    await tabs.getByRole("button", { name: "더보기" }).click();
    await page.getByRole("dialog", { name: "더보기" }).getByRole("link", { name: "내 프로필" }).click();
    await page.getByRole("textbox", { name: "닉네임" }).fill("멘토K");
    await tabs.getByRole("link", { name: "홈" }).click();
    await expect(page.getByRole("dialog", { name: "저장하지 않은 내용이 있어요" })).toBeVisible();
    await page.getByRole("button", { name: "나가기" }).click();
    await expect(page).toHaveURL(/\/$/);
  });
});
