import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { MyAssignment } from "@/features/mentor-requests/api";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { MentorProfile } from "./api";
import { addChip, bodyOf, displayNameOf, formOf, mentorProfileSchema } from "./form";
import { centerSquare, photoProblem } from "./image";
import { assignmentPeriod, sortAssignments } from "./labels";

vi.mock("./image", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./image")>()),
  // jsdom에는 canvas가 없다. 줄인 결과만 흉내 낸다
  toProfilePhoto: vi.fn<(file: Blob) => Promise<Blob>>(async () => new Blob(["webp"], { type: "image/webp" })),
}));

const MENTOR = makeMe({
  id: "u9",
  name: "김멘토",
  email: "mentor@example.com",
  phone_number: "01012345678",
  account_type: "MENTOR",
  is_super_admin: false,
});

const PROFILE: MentorProfile = {
  id: "m1",
  user_id: "u9",
  name: "김멘토",
  display_name: "김멘토",
  nickname: null,
  display_name_preference: "NAME",
  headline: "백엔드 7년차",
  introduction: "API 설계를 함께 봐요.",
  expertise: "Python, Django",
  profile_image_url: null,
  is_active: true,
};

function assignment(overrides: Partial<MyAssignment>): MyAssignment {
  return {
    id: "a1",
    cohort_id: "c12",
    bootcamp_name: "백엔드 부트캠프",
    cohort_number: 12,
    start_date: "2026-11-01",
    end_date: null,
    is_active: true,
    deactivated_at: null,
    deactivation_reason: null,
    cost_settlement_policy: "ACTUAL_DURATION",
    pay_unit: "HOURLY",
    pay_rate: 30000,
    no_show_pay_amount: 0,
    ...overrides,
  };
}

const ASSIGNMENTS = [
  assignment({ id: "a3", cohort_number: 11, start_date: "2026-05-01", end_date: "2026-10-31", is_active: false }),
  assignment({}),
  assignment({
    id: "a2",
    bootcamp_name: "프론트엔드 부트캠프",
    cohort_number: 9,
    start_date: "2026-09-01",
    end_date: "2026-12-31",
    cost_settlement_policy: "STUDENT_REQUEST",
  }),
];

function mockProfile(initial: MentorProfile = PROFILE) {
  let current = initial;
  const calls = { patch: [] as unknown[], uploads: [] as unknown[], s3: [] as string[], confirm: 0, remove: 0 };
  server.use(
    http.get(apiUrl("/api/v1/me/mentor-profile"), () => HttpResponse.json(current)),
    http.patch(apiUrl("/api/v1/me/mentor-profile"), async ({ request }) => {
      const body = (await request.json()) as Partial<MentorProfile>;
      calls.patch.push(body);
      if (body.display_name_preference === "NICKNAME" && !body.nickname)
        return HttpResponse.json(errorBody("nickname_required"), { status: 422 });
      current = { ...current, ...body };
      return HttpResponse.json(current);
    }),
    http.post(apiUrl("/api/v1/me/mentor-profile/image/uploads"), async ({ request }) => {
      calls.uploads.push(await request.json());
      return HttpResponse.json({
        upload_id: "up1",
        url: "http://s3.test/bucket",
        fields: { key: "mentors/m1/up1", policy: "p" },
        expires_at: "2026-11-24T10:00:00Z",
        max_bytes: 2097152,
      });
    }),
    http.post("http://s3.test/bucket", async ({ request }) => {
      // jsdom의 FormData는 Node 파서로 읽지 못해 본문 글자로 확인한다
      calls.s3.push(await request.text());
      return new HttpResponse(null, { status: 204 });
    }),
    http.post(apiUrl("/api/v1/me/mentor-profile/image/uploads/{upload_id}/confirm"), () => {
      calls.confirm += 1;
      current = { ...current, profile_image_url: "http://s3.test/bucket/mentors/m1/up1" };
      return HttpResponse.json(current);
    }),
    http.delete(apiUrl("/api/v1/me/mentor-profile/image"), () => {
      calls.remove += 1;
      current = { ...current, profile_image_url: null };
      return HttpResponse.json(current);
    }),
    http.get(apiUrl("/api/v1/me/mentor-assignments"), () => HttpResponse.json(ASSIGNMENTS)),
    http.get(apiUrl("/api/v1/me/password-change"), () =>
      HttpResponse.json({ available: true, state: "NONE", expires_at: null }),
    ),
  );
  return calls;
}

describe("멘토 프로필 입력 (F56)", () => {
  it("응답 ↔ 입력값, 빈 값은 null, 전문 분야는 쉼표로 잇는다", () => {
    const form = formOf(PROFILE);
    expect(form).toEqual({
      nickname: "",
      preference: "NAME",
      headline: "백엔드 7년차",
      expertise: ["Python", "Django"],
      introduction: "API 설계를 함께 봐요.",
    });
    expect(bodyOf({ ...form, nickname: " 멘토K ", headline: "  ", expertise: ["Python", "README"] })).toEqual({
      nickname: "멘토K",
      display_name_preference: "NAME",
      headline: null,
      expertise: "Python, README",
      introduction: "API 설계를 함께 봐요.",
    });
    expect(bodyOf({ ...form, expertise: [] }).expertise).toBeNull();
    expect(displayNameOf("김멘토", { nickname: "멘토K", preference: "NICKNAME" })).toBe("멘토K");
    expect(displayNameOf("김멘토", { nickname: " ", preference: "NICKNAME" })).toBe("김멘토");
  });

  it("칩은 쉼표로 나누고 빈 값·중복은 넣지 않는다", () => {
    expect(addChip(["Python"], "Django, python ,Python,, ")).toEqual(["Python", "Django", "python"]);
  });

  it("닉네임으로 보이려면 닉네임이 있어야 하고 전문 분야는 합쳐 200자까지", () => {
    const base = formOf(PROFILE);
    expect(mentorProfileSchema.safeParse({ ...base, preference: "NICKNAME" }).success).toBe(false);
    expect(mentorProfileSchema.safeParse({ ...base, expertise: ["a".repeat(148), "b".repeat(50)] }).success).toBe(true); // 쉼표·공백 2자 포함
    expect(mentorProfileSchema.safeParse({ ...base, expertise: ["a".repeat(149), "b".repeat(50)] }).success).toBe(
      false,
    );
  });

  it("사진: 형식·크기와 가운데 정사각형", () => {
    expect(photoProblem({ type: "image/gif", size: 10 })).toMatch(/PNG·JPEG·WebP/);
    expect(photoProblem({ type: "image/png", size: 11 * 1024 * 1024 })).toMatch(/10MB/);
    expect(photoProblem({ type: "image/jpeg", size: 1024 })).toBeNull();
    expect(centerSquare(1200, 800)).toEqual({ sx: 200, sy: 0, side: 800 });
    expect(centerSquare(600, 900)).toEqual({ sx: 0, sy: 150, side: 600 });
  });

  it("배정 기수는 활성 먼저, 그다음 최근 시작 순", () => {
    expect(sortAssignments(ASSIGNMENTS).map((a) => a.cohort_number)).toEqual([12, 9, 11]);
    expect(assignmentPeriod(ASSIGNMENTS[1]!)).toBe("2026.11.01 ~ 종료일 없음");
  });
});

describe("멘토 내 프로필 화면 (F56)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(MENTOR);
    URL.createObjectURL = vi.fn<(obj: Blob | MediaSource) => string>(() => "blob:preview");
    URL.revokeObjectURL = vi.fn<(url: string) => void>();
  });

  it("입력값·배정 기수·계정을 보여 주고, 바뀐 것이 없으면 저장할 수 없다", async () => {
    mockProfile();
    await renderRoute("/my/profile");
    expect(await screen.findByRole("heading", { name: "내 프로필", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "한 줄 소개" })).toHaveValue("백엔드 7년차");
    expect(screen.getByRole("textbox", { name: "이름 (실명)" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Python 빼기" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "닉네임 (먼저 적어 주세요)" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();

    const assignments = screen.getByRole("region", { name: "배정된 기수" });
    const rows = within(assignments).getAllByRole("listitem");
    expect(rows.map((r) => r.textContent)).toEqual([
      "백엔드 부트캠프 12기2026.11.01 ~ 종료일 없음 · 실제 진행 시간 정산활성",
      "프론트엔드 부트캠프 9기2026.09.01 ~ 2026.12.31 · 신청 시간 정산활성",
      "백엔드 부트캠프 11기2026.05.01 ~ 2026.10.31 · 실제 진행 시간 정산종료",
    ]);
    const account = screen.getByRole("region", { name: "계정" });
    expect(account).toHaveTextContent("mentor@example.com");
    expect(account).toHaveTextContent("010-****-5678");
    expect(within(account).getByRole("button", { name: "비밀번호 재설정" })).toBeInTheDocument();
  });

  it("닉네임·보일 이름·칩·소개를 고쳐 한 번에 저장한다", async () => {
    const calls = mockProfile();
    await renderRoute("/my/profile");
    const user = userEvent.setup();
    await user.type(await screen.findByRole("textbox", { name: "닉네임" }), "멘토K");
    await user.click(screen.getByRole("radio", { name: "닉네임 (멘토K)" }));
    await user.type(screen.getByRole("textbox", { name: "전문 분야" }), "README{Enter}");
    await user.click(screen.getByRole("button", { name: "Django 빼기" }));
    await user.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(calls.patch).toHaveLength(1));
    expect(calls.patch[0]).toEqual({
      nickname: "멘토K",
      display_name_preference: "NICKNAME",
      headline: "백엔드 7년차",
      expertise: "Python, README",
      introduction: "API 설계를 함께 봐요.",
    });
    expect(await screen.findByText("프로필을 저장했어요")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "저장" })).toBeDisabled());
    expect(calls.uploads).toEqual([]);
  });

  it("사진은 고르면 미리 보고 [저장] 때 줄인 WebP를 올려 확정한다", async () => {
    const calls = mockProfile();
    await renderRoute("/my/profile");
    const user = userEvent.setup();
    await user.upload(
      await screen.findByLabelText("프로필 사진 고르기"),
      new File(["png"], "me.png", { type: "image/png" }),
    );
    expect(await screen.findByRole("img", { name: "프로필 사진" })).toHaveAttribute("src", "blob:preview");
    expect(screen.getByText(/저장하면 바뀌어요/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(calls.confirm).toBe(1), { timeout: 3000 });
    expect(calls.patch).toEqual([]); // 글은 그대로라 보내지 않는다
    expect(calls.uploads).toEqual([{ content_type: "image/webp" }]);
    const sent = calls.s3[0]!;
    expect(sent).toMatch(/name="key"\r\n\r\nmentors\/m1\/up1/);
    expect(sent).toMatch(/name="file"; filename="[^"]+"\r\nContent-Type: image\/webp/);
    expect(sent.indexOf('name="policy"')).toBeLessThan(sent.indexOf('name="file"')); // 파일은 마지막
    expect(await screen.findByRole("img", { name: "프로필 사진" })).toHaveAttribute(
      "src",
      "http://s3.test/bucket/mentors/m1/up1",
    );
  });

  it("사진 삭제도 [저장] 때 지운다", async () => {
    const calls = mockProfile({ ...PROFILE, profile_image_url: "http://s3.test/old.webp" });
    await renderRoute("/my/profile");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "삭제" }));
    expect(screen.queryByRole("img", { name: "프로필 사진" })).not.toBeInTheDocument();
    expect(calls.remove).toBe(0);
    await user.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(calls.remove).toBe(1));
  });

  it("고르지 못하는 사진은 알려 준다", async () => {
    mockProfile();
    await renderRoute("/my/profile");
    await userEvent
      .setup({ applyAccept: false })
      .upload(await screen.findByLabelText("프로필 사진 고르기"), new File(["gif"], "me.gif", { type: "image/gif" }));
    expect(await screen.findByText("PNG·JPEG·WebP 사진만 올릴 수 있어요.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
  });

  it("수강생에게 보이는 모습은 저장하지 않은 값으로 보여 준다", async () => {
    mockProfile();
    await renderRoute("/my/profile");
    const user = userEvent.setup();
    const headline = await screen.findByRole("textbox", { name: "한 줄 소개" });
    await user.clear(headline);
    await user.type(headline, "포트폴리오 리뷰");
    await user.click(screen.getByRole("button", { name: "수강생에게 보이는 모습" }));
    const dialog = await screen.findByRole("dialog", { name: "김멘토" });
    expect(dialog).toHaveTextContent("포트폴리오 리뷰");
    expect(within(dialog).getByText("Python")).toBeInTheDocument();
    expect(dialog).toHaveTextContent("API 설계를 함께 봐요.");
  });

  it("저장하지 않고 떠나면 확인한다", async () => {
    mockProfile();
    const { router } = await renderRoute("/my/profile");
    const user = userEvent.setup();
    await user.type(await screen.findByRole("textbox", { name: "닉네임" }), "멘토K");
    await user.click(screen.getAllByRole("link", { name: "홈" })[0]!);
    const confirm = await screen.findByRole("dialog", { name: "저장하지 않은 내용이 있어요" });
    await user.click(within(confirm).getByRole("button", { name: "머무르기" }));
    expect(router.state.location.pathname).toBe("/my/profile");
    await user.click(screen.getAllByRole("link", { name: "홈" })[0]!);
    await user.click(await screen.findByRole("button", { name: "나가기" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });

  it("닉네임 없이 닉네임으로 보이게 하면 서버 오류를 알려 준다", async () => {
    mockProfile({ ...PROFILE, nickname: "멘토K", display_name_preference: "NICKNAME" });
    await renderRoute("/my/profile");
    const user = userEvent.setup();
    await user.clear(await screen.findByRole("textbox", { name: "닉네임" }));
    await user.click(screen.getByRole("button", { name: "저장" }));
    expect(await screen.findByText("닉네임으로 보이려면 닉네임을 적어 주세요.")).toBeInTheDocument();
  });
});
