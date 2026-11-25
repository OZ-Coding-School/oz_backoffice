import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { Contract, ManagerCandidate } from "./api";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: false });

function contract(id: string, extra: Partial<Contract> = {}): Contract {
  return {
    id,
    educator_type: "MENTOR",
    status: "ACTIVE",
    contractor_name: "김멘토",
    contractor_phone: "01011111234",
    contractor_email: "kim@mentor.com",
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
    ...extra,
  };
}

const ACTIVE = contract("k1");
const DRAFT = contract("k2", {
  status: "DRAFT",
  contractor_name: "박새멘토",
  title: "2026 데이터 멘토 계약",
  mentor_id: "m3",
  linked_profile: { name: "박새멘토", display_name: "박새멘토" },
  contract_file: null,
});
const INSTRUCTOR = contract("k3", {
  educator_type: "INSTRUCTOR",
  status: "ENDED",
  contractor_name: "박강사",
  title: "2026 하반기 강의 계약",
  mentor_id: null,
  linked_profile: null,
  manager_name: "이매니저",
});

const MANAGERS: ManagerCandidate[] = [
  {
    employee_id: "e1",
    name: "김관리",
    email: "boss@example.com",
    department_name: "운영",
    team_name: "운영팀",
    position_name: "팀장",
    is_me: true,
  },
  {
    employee_id: "e2",
    name: "이매니저",
    email: "lee@example.com",
    department_name: "운영",
    team_name: null,
    position_name: "매니저",
    is_me: false,
  },
];

function access(codes = ["educator.contract.read", "educator.contract.manage", "educator.mentor.read"]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: [],
  };
}

function mockApi({ codes }: { codes?: string[] } = {}) {
  const calls: { path: string; body: unknown }[] = [];
  const all = [ACTIVE, DRAFT, INSTRUCTOR];
  const byId = (id: unknown) => all.find((c) => c.id === id) ?? ACTIVE;
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes))),
    http.get(apiUrl("/api/v1/admin/contracts"), ({ request }) => {
      const p = new URL(request.url).searchParams;
      calls.push({ path: "list", body: p.toString() });
      const items = all.filter(
        (c) =>
          (!p.get("status") || c.status === p.get("status")) &&
          (!p.get("educator_type") || c.educator_type === p.get("educator_type")),
      );
      return HttpResponse.json({ items, total: items.length, limit: 20, offset: 0 });
    }),
    http.get(apiUrl("/api/v1/admin/contracts/manager-candidates"), () => HttpResponse.json(MANAGERS)),
    http.get(apiUrl("/api/v1/admin/contracts/{contract_id}"), ({ params }) =>
      HttpResponse.json(byId(params.contract_id)),
    ),
    http.post(apiUrl("/api/v1/admin/contracts/{contract_id}/confirm"), ({ params }) => {
      calls.push({ path: "confirm", body: params.contract_id });
      return HttpResponse.json({ ...byId(params.contract_id), status: "ACTIVE" });
    }),
    http.post(apiUrl("/api/v1/admin/contracts/{contract_id}/terminate"), ({ params }) => {
      calls.push({ path: "terminate", body: params.contract_id });
      return HttpResponse.json({ ...byId(params.contract_id), status: "TERMINATED" });
    }),
    http.patch(apiUrl("/api/v1/admin/contracts/{contract_id}"), async ({ request, params }) => {
      const body = await request.json();
      calls.push({ path: "update", body });
      return HttpResponse.json({ ...byId(params.contract_id), ...(body as object), manager_name: "이매니저" });
    }),
    http.post(apiUrl("/api/v1/admin/contracts"), async ({ request }) => {
      const body = await request.json();
      calls.push({ path: "create", body });
      return HttpResponse.json(contract("k9", { status: "DRAFT", ...(body as object) }), { status: 201 });
    }),
    http.get(apiUrl("/api/v1/admin/mentors"), () =>
      HttpResponse.json({
        items: [
          {
            id: "m2",
            user_id: "u2",
            name: "이멘토",
            email: "lee@mentor.com",
            phone_number: "01022225678",
            display_name: "이멘토",
            is_active: true,
            contract_count: 1,
            created_at: null,
            accepting_requests: true,
            is_registered: true,
            active_cohorts: [],
          },
        ],
        total: 1,
        limit: 20,
        offset: 0,
      }),
    ),
    http.post(apiUrl("/api/v1/admin/contracts/{contract_id}/link"), async ({ request, params }) => {
      const body = await request.json();
      calls.push({ path: "link", body });
      return HttpResponse.json({ ...byId(params.contract_id), mentor_id: "m2" });
    }),
    http.get(apiUrl("/api/v1/admin/approvals"), () => HttpResponse.json({ items: [], total: 0, limit: 1, offset: 0 })),
  );
  return calls;
}

describe("행정 업무 > 계약 (FE-18b)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("목록: 계약자·유형·제목·기간·연결·담당·상태, 유형을 고르면 주소와 요청이 바뀐다", async () => {
    const calls = mockApi();
    const { router } = await renderRoute("/admin/administration/contracts");
    const table = await screen.findByRole("table", { name: "계약" });
    expect(
      within(table)
        .getAllByRole("row")
        .slice(1)
        .map((r) =>
          within(r)
            .getAllByRole("cell")
            .map((c) => c.textContent),
        ),
    ).toEqual([
      ["김멘토", "멘토", "2026 백엔드 멘토 계약", "2026.11.01 ~ 2027.04.30", "김멘토(멘토K)", "김관리", "진행 중"],
      ["박새멘토", "멘토", "2026 데이터 멘토 계약", "2026.11.01 ~ 2027.04.30", "박새멘토", "김관리", "작성 중"],
      ["박강사", "강사", "2026 하반기 강의 계약", "2026.11.01 ~ 2027.04.30", "미연결", "이매니저", "종료"],
    ]);
    expect(screen.getByRole("navigation", { name: "모듈" })).toHaveTextContent("행정 업무");
    const user = userEvent.setup();
    await user.click(screen.getByRole("combobox", { name: "유형" }));
    await user.click(await screen.findByRole("option", { name: "강사" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ type: "INSTRUCTOR" }));
    await waitFor(() => expect(calls.at(-1)?.body).toContain("educator_type=INSTRUCTOR"));
  });

  it("진행 중 계약 패널: 정보·계약서·멘토·담당, [해지]는 확인 후", async () => {
    const calls = mockApi();
    await renderRoute("/admin/administration/contracts?contract=k1");
    const sheet = await screen.findByRole("dialog", { name: "2026 백엔드 멘토 계약" });
    expect(await within(sheet).findByRole("region", { name: "계약 정보" })).toHaveTextContent(
      "계약자김멘토휴대폰010-****-1234이메일kim@mentor.com기간2026.11.01 ~ 2027.04.30등록2026.10.28",
    );
    expect(within(sheet).getByRole("region", { name: "계약서" })).toHaveTextContent("멘토 계약서.pdf182KB");
    expect(within(sheet).getByRole("link", { name: "멘토 보기" })).toHaveAttribute(
      "href",
      "/admin/educators/mentors/m1?tab=contracts",
    );
    expect(within(sheet).queryByRole("button", { name: "확정" })).not.toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "해지" }));
    const dialog = await screen.findByRole("dialog", { name: "계약을 해지할까요?" });
    await user.click(within(dialog).getByRole("button", { name: "해지" }));
    expect(await screen.findByText("계약을 해지했어요")).toBeInTheDocument();
    expect(calls).toContainEqual({ path: "terminate", body: "k1" });
  });

  it("작성 중 계약: [수정]·[확정]·[삭제], 확정은 확인 후", async () => {
    const calls = mockApi();
    await renderRoute("/admin/administration/contracts?contract=k2");
    const sheet = await screen.findByRole("dialog", { name: "2026 데이터 멘토 계약" });
    expect(await within(sheet).findByText("없음 · 확정하려면 계약서가 필요해요")).toBeInTheDocument();
    expect(within(sheet).getByRole("button", { name: "삭제" })).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "확정" }));
    await user.click(
      within(await screen.findByRole("dialog", { name: "계약을 확정할까요?" })).getByRole("button", { name: "확정" }),
    );
    expect(await screen.findByText("계약을 확정했어요")).toBeInTheDocument();
    expect(calls).toContainEqual({ path: "confirm", body: "k2" });
  });

  it("담당 직원 변경과 다른 멘토로 옮기기", async () => {
    const calls = mockApi();
    await renderRoute("/admin/administration/contracts?contract=k1");
    const sheet = await screen.findByRole("dialog", { name: "2026 백엔드 멘토 계약" });
    const user = userEvent.setup();
    await user.click(await within(sheet).findByRole("button", { name: "변경" }));
    const managerDialog = await screen.findByRole("dialog", { name: "담당 직원 변경" });
    await user.click(await within(managerDialog).findByRole("option", { name: /이매니저/ }));
    await user.click(within(managerDialog).getByRole("button", { name: "변경" }));
    expect(await screen.findByText("담당 직원을 이매니저(으)로 바꿨어요")).toBeInTheDocument();
    expect(calls).toContainEqual({ path: "update", body: { manager_employee_id: "e2" } });

    await user.click(within(sheet).getByRole("button", { name: "다른 멘토로 옮기기" }));
    const move = await screen.findByRole("dialog", { name: "다른 멘토로 옮기기" });
    await user.click(await within(move).findByRole("option", { name: /이멘토/ }));
    await user.click(within(move).getByRole("button", { name: "옮기기" }));
    expect(await screen.findByText("계약을 이멘토 멘토로 옮겼어요")).toBeInTheDocument();
    expect(calls).toContainEqual({ path: "link", body: { mentor_id: "m2" } });
  });

  it("계약 추가: 담당은 처음에 나, 저장하면 작성 중으로 만들고 그 계약 패널을 연다", async () => {
    const calls = mockApi();
    const { router } = await renderRoute("/admin/administration/contracts");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "계약 추가" }));
    const form = await screen.findByRole("form", { name: "계약 추가" });
    await user.type(within(form).getByLabelText("계약자 이름"), "이멘토");
    await user.type(within(form).getByLabelText("휴대폰"), "010-2222-5678");
    await user.type(within(form).getByLabelText("제목"), "2026 데이터 멘토 계약");
    await user.type(within(form).getByLabelText("시작일"), "2026-12-01");
    await user.type(within(form).getByLabelText("종료일"), "2027-05-31");
    expect(await within(form).findByRole("option", { name: /김관리 \(나\)/ })).toHaveAttribute("aria-selected", "true");
    await user.click(within(form).getByRole("button", { name: "저장" }));
    expect(await screen.findByText("계약을 작성 중으로 저장했어요")).toBeInTheDocument();
    expect(calls).toContainEqual({
      path: "create",
      body: {
        educator_type: "MENTOR",
        contractor_name: "이멘토",
        contractor_phone: "010-2222-5678",
        contractor_email: null,
        title: "2026 데이터 멘토 계약",
        start_date: "2026-12-01",
        end_date: "2027-05-31",
        manager_employee_id: "e1",
        contract_file_id: null,
      },
    });
    await waitFor(() => expect(router.state.location.search).toEqual({ contract: "k9" }));
  });

  it("조회 권한만 있으면 추가·변경 버튼이 없다", async () => {
    mockApi({ codes: ["educator.contract.read"] });
    await renderRoute("/admin/administration/contracts?contract=k1");
    const sheet = await screen.findByRole("dialog", { name: "2026 백엔드 멘토 계약" });
    await within(sheet).findByRole("region", { name: "계약 정보" });
    expect(within(sheet).queryByRole("button", { name: "해지" })).not.toBeInTheDocument();
    expect(within(sheet).queryByRole("button", { name: "변경" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "계약 추가" })).not.toBeInTheDocument();
  });
});
