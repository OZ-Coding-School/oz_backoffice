import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { Member, MemberDetail } from "./api";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: false });

function member(id: string, name: string, extra: Partial<Member> = {}): Member {
  return {
    id,
    name,
    email: `${id}@gmail.com`,
    phone_number: "01012341234",
    account_type: "STUDENT",
    is_active: true,
    is_super_admin: false,
    approved_at: "2025-11-03T01:00:00Z",
    last_login_at: "2025-11-24T12:40:00Z",
    ...extra,
  };
}

const KIM = member("u1", "김수강");
const PARK = member("u2", "박회원", { is_active: false });
const LEE = member("u3", "이멘토", { account_type: "MENTOR" });
const CHOI = member("u4", "최운영", { account_type: "STAFF", is_super_admin: true });

function detail(m: Member, extra: Partial<MemberDetail> = {}): MemberDetail {
  return {
    ...m,
    enrollments: [],
    assignments: [],
    contract_count: null,
    department_name: null,
    team_name: null,
    position_name: null,
    history: [],
    ...extra,
  };
}

const DETAILS: Record<string, MemberDetail> = {
  u1: detail(KIM, { enrollments: [{ bootcamp_name: "백엔드 부트캠프", cohort_number: 12, status: "ENROLLED" }] }),
  u2: detail(PARK, {
    history: [{ action: "DEACTIVATE", reason: "계정 공유", actor_name: "김관리", at: "2025-11-22T06:10:00Z" }],
  }),
  u3: detail(LEE, {
    contract_count: 2,
    assignments: [
      { bootcamp_name: "백엔드 부트캠프", cohort_number: 12, active: true },
      { bootcamp_name: "백엔드 부트캠프", cohort_number: 11, active: false },
    ],
  }),
  u4: detail(CHOI, { department_name: "교육운영본부", team_name: null, position_name: "운영 매니저" }),
};

function access(codes: string[]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: [],
  };
}

function mockApi({ codes = ["member.user.read", "member.user.manage"] } = {}) {
  const queries: URLSearchParams[] = [];
  const posts: { path: string; body: unknown }[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes))),
    http.get(apiUrl("/api/v1/admin/users"), ({ request }) => {
      const params = new URL(request.url).searchParams;
      queries.push(params);
      const type = params.get("account_type");
      const items = [KIM, PARK, LEE, CHOI].filter((m) => !type || m.account_type === type);
      return HttpResponse.json({
        items,
        total: items.length,
        limit: 20,
        offset: 0,
        counts: { ALL: 4, STUDENT: 2, MENTOR: 1, STAFF: 1 },
      });
    }),
    http.get(apiUrl("/api/v1/admin/users/{user_id}"), ({ params }) =>
      HttpResponse.json(DETAILS[String(params.user_id)]),
    ),
    http.post(apiUrl("/api/v1/admin/users/{user_id}/deactivate"), async ({ request, params }) => {
      posts.push({ path: "deactivate", body: await request.json() });
      return HttpResponse.json({ ...DETAILS[String(params.user_id)], is_active: false });
    }),
    http.post(apiUrl("/api/v1/admin/users/{user_id}/activate"), async ({ request, params }) => {
      posts.push({ path: "activate", body: await request.json() });
      return HttpResponse.json({ ...DETAILS[String(params.user_id)], is_active: true });
    }),
  );
  return { queries, posts };
}

describe("회원 관리 > 전체 회원 (FE-15i)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("종류 탭·건수, 휴대폰 가림, 상태 배지, 메뉴", async () => {
    const { queries } = mockApi();
    const { router } = await renderRoute("/admin/members/users");
    const table = await screen.findByRole("table", { name: "회원" });
    expect(within(table).getByRole("row", { name: "김수강" })).toHaveTextContent("010-****-1234");
    expect(within(table).getByRole("row", { name: "박회원" })).toHaveTextContent("비활성");
    expect(within(table).getByRole("row", { name: "최운영" })).toHaveTextContent("최고 관리자");
    const tabs = screen.getByRole("navigation", { name: "계정 종류" });
    expect(within(tabs).getByRole("link", { name: "전체 4" })).toHaveAttribute("aria-current", "page");
    const menu = screen.getByRole("navigation", { name: "메뉴" });
    expect(within(menu).getByRole("link", { name: "전체 회원" })).toHaveAttribute("aria-current", "page");

    const user = userEvent.setup();
    await user.click(within(tabs).getByRole("link", { name: "멘토 1" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "mentor" }));
    await waitFor(() => expect(queries.at(-1)?.get("account_type")).toBe("MENTOR"));
  });

  it("검색어는 입력이 멈추면 주소와 요청에 반영된다", async () => {
    const { queries } = mockApi();
    const { router } = await renderRoute("/admin/members/users");
    await screen.findByRole("table", { name: "회원" });
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox", { name: "회원 검색" }), "김수");
    await waitFor(() => expect(router.state.location.search).toEqual({ q: "김수" }));
    await waitFor(() => expect(queries.at(-1)?.get("q")).toBe("김수"));
  });

  it("종류별 연결 정보: 수강·배정·소속, 이력", async () => {
    mockApi();
    await renderRoute("/admin/members/users?user=u1");
    let sheet = await screen.findByRole("dialog", { name: "김수강" });
    expect(await within(sheet).findByRole("list", { name: "수강" })).toHaveTextContent("백엔드 부트캠프 12기수강 중");

    await renderRoute("/admin/members/users?user=u3");
    sheet = await screen.findByRole("dialog", { name: "이멘토" });
    const assigned = await within(sheet).findByRole("list", { name: "배정" });
    expect(assigned).toHaveTextContent("12기배정 중");
    expect(assigned).toHaveTextContent("11기종료");
    expect(within(sheet).getByRole("region", { name: "배정" })).toHaveTextContent("계약2건");

    await renderRoute("/admin/members/users?user=u4");
    sheet = await screen.findByRole("dialog", { name: "최운영" });
    expect(await within(sheet).findByRole("region", { name: "소속" })).toHaveTextContent("팀팀 없음");

    await renderRoute("/admin/members/users?user=u2");
    sheet = await screen.findByRole("dialog", { name: "박회원" });
    expect(await within(sheet).findByRole("list", { name: "이력" })).toHaveTextContent("비활성화 · 김관리");
    expect(within(sheet).getByRole("list", { name: "이력" })).toHaveTextContent("계정 공유");
  });

  it("비활성화는 사유가 있어야 하고, 처리하면 상태가 바뀐다", async () => {
    const { posts } = mockApi();
    await renderRoute("/admin/members/users?user=u1");
    const sheet = await screen.findByRole("dialog", { name: "김수강" });
    const user = userEvent.setup();
    await user.click(await within(sheet).findByRole("button", { name: "비활성화" }));
    const dialog = await screen.findByRole("dialog", { name: "김수강 계정을 비활성화할까요?" });
    const confirm = within(dialog).getByRole("button", { name: "비활성화" });
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByRole("textbox", { name: "비활성화 사유" }), "부정 사용");
    await user.click(confirm);
    await waitFor(() => expect(posts).toEqual([{ path: "deactivate", body: { reason: "부정 사용" } }]));
    expect(await screen.findByText("김수강 계정을 비활성화했어요")).toBeInTheDocument();
    expect(await within(sheet).findByRole("button", { name: "활성화" })).toBeInTheDocument();
  });

  it("비활성 계정은 사유 없이 활성화할 수 있다", async () => {
    const { posts } = mockApi();
    await renderRoute("/admin/members/users?user=u2");
    const sheet = await screen.findByRole("dialog", { name: "박회원" });
    const user = userEvent.setup();
    await user.click(await within(sheet).findByRole("button", { name: "활성화" }));
    const dialog = await screen.findByRole("dialog", { name: "박회원 계정을 활성화할까요?" });
    await user.click(within(dialog).getByRole("button", { name: "활성화" }));
    await waitFor(() => expect(posts).toEqual([{ path: "activate", body: { reason: null } }]));
  });

  it("조회 권한만 있으면 비활성화 버튼이 없다", async () => {
    mockApi({ codes: ["member.user.read"] });
    await renderRoute("/admin/members/users?user=u1");
    const sheet = await screen.findByRole("dialog", { name: "김수강" });
    await within(sheet).findByRole("list", { name: "수강" });
    expect(within(sheet).queryByRole("button", { name: "비활성화" })).not.toBeInTheDocument();
  });
});
