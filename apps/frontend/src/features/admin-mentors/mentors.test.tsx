import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { MentorProfile } from "@/features/mentor-profile/api";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { Contract } from "@/features/admin-contracts/api";

import type { MentorAssignment, MentorItem } from "./api";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: false });

function mentor(id: string, name: string, extra: Partial<MentorItem> = {}): MentorItem {
  return {
    id,
    user_id: `u-${id}`,
    name,
    email: `${id}@mentor.com`,
    phone_number: "01011111234",
    display_name: name,
    is_active: true,
    contract_count: 1,
    created_at: "2026-11-03T01:00:00Z",
    accepting_requests: true,
    is_registered: true,
    active_cohorts: [],
    ...extra,
  };
}

const KIM = mentor("m1", "김멘토", {
  display_name: "멘토K",
  contract_count: 2,
  active_cohorts: [
    { cohort_id: "c12", bootcamp_name: "백엔드", cohort_number: 12 },
    { cohort_id: "d3", bootcamp_name: "데이터 분석", cohort_number: 3 },
  ],
});
const CHOI = mentor("m2", "최멘토", { is_active: false, accepting_requests: false, contract_count: 0 });
const NEW = mentor("m3", "박새멘토", {
  user_id: null,
  email: null,
  phone_number: "01055550000",
  is_active: false,
  accepting_requests: false,
  is_registered: false,
  created_at: "2026-11-24T01:00:00Z",
});

const PROFILE: MentorProfile = {
  id: "m1",
  user_id: "u-m1",
  name: "김멘토",
  display_name: "멘토K",
  nickname: "멘토K",
  display_name_preference: "NICKNAME",
  headline: "백엔드 7년 차, 실무 코드 리뷰",
  introduction: "## 이런 분께 추천해요\n- 첫 백엔드 포트폴리오",
  expertise: "백엔드, 코드 리뷰",
  profile_image_url: null,
  is_active: true,
};

function assignment(id: string, extra: Partial<MentorAssignment> = {}): MentorAssignment {
  return {
    id,
    cohort_id: `c-${id}`,
    bootcamp_name: "백엔드 부트캠프",
    cohort_number: 12,
    start_date: "2026-11-02",
    end_date: null,
    is_active: true,
    deactivated_at: null,
    deactivation_reason: null,
    cost_settlement_policy: "ACTUAL_DURATION",
    pay_unit: "HOURLY",
    pay_rate: 30000,
    no_show_pay_amount: 10000,
    ...extra,
  };
}

const ASSIGNMENTS = [
  assignment("a1"),
  assignment("a2", {
    cohort_id: "c-d3",
    bootcamp_name: "데이터 분석 부트캠프",
    cohort_number: 3,
    pay_unit: "PER_SESSION",
    pay_rate: 50000,
    no_show_pay_amount: 0,
    start_date: "2026-11-16",
    end_date: "2027-02-28",
  }),
  assignment("a3", {
    cohort_number: 11,
    start_date: "2025-12-01",
    end_date: "2026-05-29",
    is_active: false,
    deactivated_at: "2026-05-29T15:05:00Z",
    deactivation_reason: "EXPIRED",
  }),
];

const CONTRACTS: Contract[] = [
  {
    id: "k1",
    educator_type: "MENTOR",
    status: "ACTIVE",
    contractor_name: "김멘토",
    contractor_phone: "01011111234",
    contractor_email: null,
    title: "2026 백엔드 멘토 계약",
    start_date: "2026-11-01",
    end_date: "2027-04-30",
    manager_employee_id: "e1",
    manager_name: "김관리",
    mentor_id: "m1",
    instructor_id: null,
    linked_profile: { name: "김멘토", display_name: "멘토K" },
    contract_file: { id: "f1", file_name: "멘토 계약서.pdf", file_size: 186_000, created_at: "2026-10-28T01:00:00Z" },
    created_at: "2026-10-28T01:00:00Z",
    updated_at: null,
  },
];

const COHORTS = [
  {
    id: "c-a1",
    bootcamp_id: "b1",
    bootcamp_name: "백엔드 부트캠프",
    cohort_number: 12,
    start_date: "2026-06-02",
    end_date: "2026-11-30",
    status: "ONGOING",
  },
  {
    id: "c-d3",
    bootcamp_id: "b2",
    bootcamp_name: "데이터 분석 부트캠프",
    cohort_number: 3,
    start_date: "2026-11-16",
    end_date: "2027-04-30",
    status: "PLANNED",
  },
  {
    id: "c-d4",
    bootcamp_id: "b2",
    bootcamp_name: "데이터 분석 부트캠프",
    cohort_number: 4,
    start_date: "2027-05-01",
    end_date: "2027-10-31",
    status: "PLANNED",
  },
] as StaffAccess["cohorts"];

function access(
  codes = ["educator.mentor.read", "educator.mentor.manage", "educator.contract.read", "mentoring.assignment.manage"],
): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: COHORTS,
  };
}

function mockApi({ codes, item = KIM }: { codes?: string[]; item?: MentorItem } = {}) {
  const calls: { path: string; body: unknown }[] = [];
  const record = async (path: string, request: Request) => {
    const text = await request.text();
    calls.push({ path, body: text ? (JSON.parse(text) as unknown) : null });
  };
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes))),
    http.get(apiUrl("/api/v1/admin/mentors"), ({ request }) => {
      const url = new URL(request.url);
      const status = url.searchParams.get("status");
      const items = [KIM, CHOI, NEW].filter(
        (m) =>
          (status === null ||
            (status === "pending" ? !m.is_registered : m.is_registered && m.is_active === (status === "active"))) &&
          (!url.searchParams.get("q") || m.name.includes(url.searchParams.get("q") ?? "")),
      );
      return HttpResponse.json({ items, total: items.length, limit: 20, offset: 0 });
    }),
    http.get(apiUrl("/api/v1/admin/mentors/{mentor_id}"), () => HttpResponse.json(item)),
    http.get(apiUrl("/api/v1/admin/mentors/{mentor_id}/profile"), () => HttpResponse.json(PROFILE)),
    http.get(apiUrl("/api/v1/admin/mentors/{mentor_id}/mentor-assignments"), () => HttpResponse.json(ASSIGNMENTS)),
    http.post(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentor-assignments"), async ({ request, params }) => {
      calls.push({ path: `create:${String(params.cohort_id)}`, body: await request.json() });
      return HttpResponse.json(
        { ...ASSIGNMENTS[0], id: "a9", mentor_id: "m1", mentor_name: "김멘토", mentor_display_name: "멘토K" },
        { status: 201 },
      );
    }),
    http.patch(
      apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentor-assignments/{assignment_id}"),
      async ({ request, params }) => {
        calls.push({ path: `update:${String(params.assignment_id)}`, body: await request.json() });
        return HttpResponse.json({
          ...ASSIGNMENTS[0],
          mentor_id: "m1",
          mentor_name: "김멘토",
          mentor_display_name: "멘토K",
        });
      },
    ),
    http.delete(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentor-assignments/{assignment_id}"), ({ params }) => {
      calls.push({ path: `end:${String(params.assignment_id)}`, body: null });
      return HttpResponse.json({
        ...ASSIGNMENTS[0],
        is_active: false,
        mentor_id: "m1",
        mentor_name: "김멘토",
        mentor_display_name: "멘토K",
        canceled_pending_requests: 2,
      });
    }),
    http.post(
      apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentor-assignments/{assignment_id}/reactivate"),
      ({ params }) => {
        calls.push({ path: `reactivate:${String(params.assignment_id)}`, body: null });
        return HttpResponse.json({
          ...ASSIGNMENTS[2],
          is_active: true,
          mentor_id: "m1",
          mentor_name: "김멘토",
          mentor_display_name: "멘토K",
        });
      },
    ),
    http.get(apiUrl("/api/v1/admin/contracts"), ({ request }) => {
      calls.push({ path: "contracts", body: new URL(request.url).searchParams.get("mentor_id") });
      return HttpResponse.json({ items: CONTRACTS, total: CONTRACTS.length, limit: 100, offset: 0 });
    }),
    http.patch(apiUrl("/api/v1/admin/mentors/{mentor_id}/profile"), async ({ request }) => {
      await record("profile", request.clone());
      return HttpResponse.json({ ...PROFILE, ...((await request.json()) as object) });
    }),
    http.put(apiUrl("/api/v1/admin/mentors/{mentor_id}/schedule/accepting"), async ({ request }) => {
      await record("accepting", request);
      return HttpResponse.json({ mentor_id: "m1", accepting_requests: false, canceled_pending_requests: 2 });
    }),
    http.post(apiUrl("/api/v1/admin/mentors/{mentor_id}/deactivate"), async ({ request }) => {
      const body = (await request.json()) as { confirm: boolean };
      calls.push({ path: "deactivate", body });
      return HttpResponse.json({
        mentor_id: "m1",
        is_active: !body.confirm,
        applied: body.confirm,
        notice: "",
        assignments: [{ ...ASSIGNMENTS[0], mentor_id: "m1", mentor_name: "김멘토" }],
        pending_requests: 3,
      });
    }),
    http.post(apiUrl("/api/v1/admin/mentors/{mentor_id}/activate"), () => {
      calls.push({ path: "activate", body: null });
      return HttpResponse.json({
        mentor_id: "m2",
        is_active: true,
        restorable: [{ ...ASSIGNMENTS[0], mentor_id: "m2", mentor_name: "최멘토" }],
      });
    }),
    http.post(apiUrl("/api/v1/admin/mentors/{mentor_id}/mentor-assignments/reactivate"), async ({ request }) => {
      await record("reactivate", request);
      return HttpResponse.json({ reactivated: [ASSIGNMENTS[0]], failed: [] });
    }),
  );
  return calls;
}

describe("강사·멘토 > 멘토 (FE-18a)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("목록: 이름(닉네임)·이메일·휴대폰(가림)·계약·신청 받기·상태를 칸마다", async () => {
    mockApi();
    await renderRoute("/admin/educators/mentors");
    const table = await screen.findByRole("table", { name: "멘토" });
    const rows = within(table).getAllByRole("row").slice(1);
    const cells = (row: HTMLElement) =>
      within(row)
        .getAllByRole("cell")
        .map((c) => c.textContent);
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["이름(닉네임)", "이메일", "휴대폰", "계약", "신청 받기", "상태"]);
    expect(rows.map(cells)).toEqual([
      ["김멘토(멘토K)", "m1@mentor.com", "010-****-1234", "2건", "신청 받는 중", "활성"],
      ["최멘토", "m2@mentor.com", "010-****-1234", "0건", "신청 꺼짐", "비활성"],
      ["박새멘토", "—", "010-****-0000", "1건", "신청 꺼짐", "가입 전"],
    ]);
    expect(screen.getByRole("link", { name: "멘토" })).toHaveAttribute("href", "/admin/educators/mentors");
  });

  it("상태를 고르면 주소와 목록이 바뀌고, 행을 누르면 상세", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/educators/mentors");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("combobox", { name: "상태" }));
    await user.click(await screen.findByRole("option", { name: "비활성" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ status: "inactive" }));
    const table = await screen.findByRole("table", { name: "멘토" });
    await waitFor(() => expect(within(table).getAllByRole("row")).toHaveLength(2));
    await user.click(within(table).getByRole("link", { name: "최멘토" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/admin/educators/mentors/m2"));
  });

  it("상세 프로필: 수강생에게 보이는 모습(마크다운 소개)·계정·신청 받기", async () => {
    mockApi();
    await renderRoute("/admin/educators/mentors/m1");
    expect(await screen.findByRole("heading", { level: 1, name: "김멘토" })).toBeInTheDocument();
    const view = await screen.findByRole("region", { name: "수강생에게 보이는 모습" });
    expect(within(view).getByRole("heading", { name: "이런 분께 추천해요" })).toBeInTheDocument();
    expect(within(view).getByText("백엔드 7년 차, 실무 코드 리뷰")).toBeInTheDocument();
    const account = screen.getByRole("region", { name: "계정" });
    expect(account).toHaveTextContent("실명김멘토이메일m1@mentor.com휴대폰010-****-1234가입2026.11.03 승인");
    expect(screen.getByRole("switch", { name: "신청 받기" })).toBeChecked();
  });

  it("신청 받기를 끄면 확인 후 운영진 API로 바꾼다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/educators/mentors/m1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("switch", { name: "신청 받기" }));
    await user.click(await screen.findByRole("button", { name: "끄기" }));
    expect(await screen.findByText("신청 받기를 껐어요. 대기 중인 신청 2건을 취소했어요")).toBeInTheDocument();
    expect(calls).toContainEqual({ path: "accepting", body: { accepting_requests: false } });
  });

  it("프로필 수정: 같은 자리에서 고치고 미리보기에 반영, 저장하면 조회로 돌아간다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/educators/mentors/m1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "프로필 수정" }));
    const form = await screen.findByRole("form", { name: "프로필 수정" });
    const headline = within(form).getByRole("textbox", { name: "한 줄 소개" });
    await user.clear(headline);
    await user.type(headline, "데이터 엔지니어");
    expect(screen.getByRole("region", { name: "수강생에게 보이는 모습" })).toHaveTextContent("데이터 엔지니어");
    await user.click(within(form).getByRole("tab", { name: "미리보기" }));
    expect(within(form).getByRole("heading", { name: "이런 분께 추천해요" })).toBeInTheDocument();
    await user.click(within(form).getByRole("button", { name: "저장" }));
    expect(await screen.findByText("프로필을 저장했어요")).toBeInTheDocument();
    expect(calls).toContainEqual({ path: "profile", body: expect.objectContaining({ headline: "데이터 엔지니어" }) });
    expect(await screen.findByRole("button", { name: "프로필 수정" })).toBeInTheDocument();
  });

  it("관리 권한이 없으면 수정·비활성화가 없고 스위치는 막힌다", async () => {
    mockApi({ codes: ["educator.mentor.read"] });
    await renderRoute("/admin/educators/mentors/m1");
    await screen.findByRole("region", { name: "수강생에게 보이는 모습" });
    expect(screen.queryByRole("button", { name: "프로필 수정" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "비활성화" })).not.toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "신청 받기" })).toBeDisabled();
  });

  it("배정 탭: 카드를 세로로, 활성 먼저, 종료 사유", async () => {
    mockApi();
    await renderRoute("/admin/educators/mentors/m1?tab=assignments");
    const list = await screen.findByRole("list", { name: "배정" });
    expect(
      within(list)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual([
      "백엔드 부트캠프 12기배정 중기간2026.11.02 ~ 종료일 없음정산실제 진행 시간 기준 · 시간당 30,000원 · 노쇼 10,000원",
      "데이터 분석 부트캠프 3기배정 중기간2026.11.16 ~ 2027.02.28정산세션당 50,000원 · 노쇼 없음",
      "백엔드 부트캠프 11기종료기간2025.12.01 ~ 2026.05.29정산실제 진행 시간 기준 · 시간당 30,000원 · 노쇼 10,000원종료기간 만료로 종료 · 2026.05.30",
    ]);
  });

  it("비활성화: 함께 꺼질 배정과 대기 신청을 보여 주고 확인하면 적용", async () => {
    const calls = mockApi();
    await renderRoute("/admin/educators/mentors/m1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "비활성화" }));
    const dialog = await screen.findByRole("dialog", { name: "김멘토 멘토를 비활성화할까요?" });
    expect(dialog).toHaveTextContent("함께 꺼지는 배정 1개백엔드 부트캠프 12기");
    expect(dialog).toHaveTextContent("대기 중인 신청 3건은 자동으로 취소돼요.");
    await user.click(within(dialog).getByRole("button", { name: "비활성화" }));
    expect(await screen.findByText("멘토를 비활성화했어요. 대기 중인 신청 3건을 취소했어요")).toBeInTheDocument();
    expect(calls.filter((c) => c.path === "deactivate").map((c) => c.body)).toEqual([
      { confirm: false },
      { confirm: true },
    ]);
  });

  it("활성화 후 다시 켤 배정을 고른다", async () => {
    const calls = mockApi({ item: CHOI });
    await renderRoute("/admin/educators/mentors/m2");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "활성화" }));
    const confirm = await screen.findByRole("dialog", { name: "최멘토 멘토를 활성화할까요?" });
    await user.click(within(confirm).getByRole("button", { name: "활성화" }));
    const pick = await screen.findByRole("dialog", { name: "배정을 다시 켤까요?" });
    expect(within(pick).getByRole("checkbox", { name: "백엔드 부트캠프 12기" })).toBeChecked();
    await user.click(within(pick).getByRole("button", { name: "다시 켜기" }));
    expect(await screen.findByText("배정 1개를 다시 켰어요")).toBeInTheDocument();
    expect(calls).toContainEqual({ path: "reactivate", body: { assignment_ids: ["a1"] } });
  });

  it("계약 탭: 그 멘토의 계약 카드, 누르면 행정 업무 › 계약 패널로", async () => {
    const calls = mockApi();
    const { router } = await renderRoute("/admin/educators/mentors/m1?tab=contracts");
    const list = await screen.findByRole("list", { name: "계약" });
    expect(within(list).getByRole("listitem")).toHaveTextContent(
      "2026 백엔드 멘토 계약진행 중기간2026.11.01 ~ 2027.04.30계약서멘토 계약서.pdf담당김관리",
    );
    expect(calls).toContainEqual({ path: "contracts", body: "m1" });
    await userEvent.setup().click(within(list).getByRole("link", { name: "2026 백엔드 멘토 계약" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/admin/administration/contracts"));
    expect(router.state.location.search).toEqual({ contract: "k1" });
  });

  it("계약 조회 권한이 없으면 계약 탭이 없다", async () => {
    mockApi({ codes: ["educator.mentor.read"] });
    await renderRoute("/admin/educators/mentors/m1");
    await screen.findByRole("region", { name: "수강생에게 보이는 모습" });
    expect(screen.queryByRole("link", { name: "계약" })).not.toBeInTheDocument();
  });

  it("가입 전 멘토: 활성화 버튼 없이 가입 전 배지, 계정 칸은 가입 전, 신청 받기는 막힘", async () => {
    mockApi({ item: NEW });
    await renderRoute("/admin/educators/mentors/m3");
    expect(await screen.findByRole("heading", { level: 1, name: "박새멘토" })).toBeInTheDocument();
    expect(screen.getByText("가입 전 · 계약을 먼저 만든 멘토예요")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "활성화" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "비활성화" })).not.toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "계정" })).toHaveTextContent(
      "이름박새멘토휴대폰010-****-0000가입가입 전",
    );
    expect(screen.getByRole("switch", { name: "신청 받기" })).toBeDisabled();
  });

  it("배정 패널: 기수·기간·정산 조건 조회, [수정]은 같은 구성에서 저장", async () => {
    const calls = mockApi();
    await renderRoute("/admin/educators/mentors/m1?tab=assignments&assignment=a1");
    const sheet = await screen.findByRole("dialog", { name: "백엔드 부트캠프 12기" });
    expect(await within(sheet).findByRole("region", { name: "기수" })).toHaveTextContent(
      "과정백엔드 부트캠프기수12기기수 기간2026.06.02 ~ 2026.11.30기수 상태진행 중",
    );
    expect(within(sheet).getByRole("region", { name: "정산 조건" })).toHaveTextContent(
      "실제 진행 시간단가 기준시간당단가30,000원노쇼 단가10,000원",
    );
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "수정" }));
    const form = await within(sheet).findByRole("form", { name: "배정 수정" });
    expect(within(sheet).getByText("수정 중")).toBeInTheDocument();
    await user.click(within(form).getByRole("radio", { name: "세션당" }));
    const rate = within(form).getByLabelText("단가");
    await user.clear(rate);
    await user.type(rate, "50,000");
    await user.click(within(form).getByRole("button", { name: "저장" }));
    expect(await screen.findByText("백엔드 부트캠프 12기 배정을 저장했어요")).toBeInTheDocument();
    expect(calls).toContainEqual({
      path: "update:a1",
      body: {
        start_date: "2026-11-02",
        end_date: null,
        cost_settlement_policy: "ACTUAL_DURATION",
        pay_unit: "PER_SESSION",
        pay_rate: 50000,
        no_show_pay_amount: 10000,
      },
    });
  });

  it("배정 종료는 확인 후, 종료된 배정은 [다시 켜기]", async () => {
    const calls = mockApi();
    await renderRoute("/admin/educators/mentors/m1?tab=assignments&assignment=a1");
    const sheet = await screen.findByRole("dialog", { name: "백엔드 부트캠프 12기" });
    const user = userEvent.setup();
    await user.click(await within(sheet).findByRole("button", { name: "배정 종료" }));
    const dialog = await screen.findByRole("dialog", { name: "백엔드 부트캠프 12기 배정을 종료할까요?" });
    await user.click(within(dialog).getByRole("button", { name: "배정 종료" }));
    expect(await screen.findByText("배정을 종료했어요. 대기 중인 신청 2건을 취소했어요")).toBeInTheDocument();
    expect(calls).toContainEqual({ path: "end:a1", body: null });
  });

  it("종료된 배정: 종료 섹션과 [다시 켜기]", async () => {
    const calls = mockApi();
    await renderRoute("/admin/educators/mentors/m1?tab=assignments&assignment=a3");
    const sheet = await screen.findByRole("dialog", { name: "백엔드 부트캠프 11기" });
    expect(await within(sheet).findByRole("region", { name: "종료" })).toHaveTextContent("사유기간 만료로 종료");
    await userEvent.setup().click(within(sheet).getByRole("button", { name: "다시 켜기" }));
    expect(await screen.findByText("백엔드 부트캠프 11기 배정을 다시 켰어요")).toBeInTheDocument();
    expect(calls).toContainEqual({ path: "reactivate:a3", body: null });
  });

  it("배정 추가: 과정 → 기수(이미 배정 중인 기수는 막힘) → 기간·정산 조건", async () => {
    const calls = mockApi();
    const { router } = await renderRoute("/admin/educators/mentors/m1?tab=assignments");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "배정 추가" }));
    const form = await screen.findByRole("form", { name: "배정 추가" });
    expect(within(form).queryByRole("combobox", { name: "기수" })).not.toBeInTheDocument();
    await user.click(within(form).getByRole("combobox", { name: "과정" }));
    await user.click(await screen.findByRole("option", { name: "데이터 분석 부트캠프" }));
    await user.click(within(form).getByRole("combobox", { name: "기수" }));
    expect(await screen.findByRole("option", { name: "3기 · 2026.11.16 ~ 2027.04.30 · 배정 중" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    await user.click(screen.getByRole("option", { name: "4기 · 2027.05.01 ~ 2027.10.31" }));
    await user.type(within(form).getByLabelText("시작일"), "2027-05-01");
    await user.type(within(form).getByLabelText("단가"), "40000");
    await user.click(within(form).getByRole("button", { name: "추가" }));
    expect(await screen.findByText("데이터 분석 부트캠프 4기에 배정했어요")).toBeInTheDocument();
    expect(calls).toContainEqual({
      path: "create:c-d4",
      body: {
        mentor_id: "m1",
        start_date: "2027-05-01",
        end_date: null,
        cost_settlement_policy: "ACTUAL_DURATION",
        pay_unit: "HOURLY",
        pay_rate: 40000,
        no_show_pay_amount: 0,
      },
    });
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "assignments", assignment: "a9" }));
  });

  it("가입 전 멘토나 배정 관리 권한이 없으면 [배정 추가]가 없다", async () => {
    mockApi({ item: NEW });
    await renderRoute("/admin/educators/mentors/m3?tab=assignments");
    await screen.findByText(/배정 3건/);
    expect(screen.queryByRole("button", { name: "배정 추가" })).not.toBeInTheDocument();
  });
});
