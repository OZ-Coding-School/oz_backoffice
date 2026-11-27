import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffAccess, StaffCohort } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { Amendment, Contract, ManagerCandidate } from "./api";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: false });

const COHORTS: StaffCohort[] = [
  {
    id: "c11",
    bootcamp_id: "b1",
    bootcamp_name: "백엔드 부트캠프",
    cohort_number: 11,
    start_date: "2026-03-01",
    end_date: "2026-08-31",
    status: "ENDED",
  },
  {
    id: "c12",
    bootcamp_id: "b1",
    bootcamp_name: "백엔드 부트캠프",
    cohort_number: 12,
    start_date: "2026-09-01",
    end_date: "2027-02-28",
    status: "ONGOING",
  },
];

function contract(id: string, extra: Partial<Contract> = {}): Contract {
  return {
    id,
    contract_type: "MENTOR",
    bootcamp_id: "b1",
    bootcamp_name: "백엔드 부트캠프",
    cohort_id: "c12",
    cohort_number: 12,
    business_registration_number: null,
    contact_person_name: null,
    settlement_type: "UNIT_PRICE",
    total_amount: null,
    unit_price: 50000,
    price_unit: "HOURLY",
    vat_type: "NOT_APPLICABLE",
    amount_note: null,
    no_show_pay_amount: 20000,
    mentoring_time_basis: "ACTUAL_DURATION",
    cancel_reason: null,
    canceled_on: null,
    termination_reason: null,
    termination_detail: null,
    terminated_on: null,
    status: "ACTIVE",
    contractor_name: "김멘토",
    contractor_phone: "01011111234",
    contractor_email: "kim@mentor.com",
    title: "12기 백엔드 멘토 계약",
    start_date: "2026-09-01",
    end_date: "2027-02-28",
    manager_employee_id: "e1",
    manager_name: "김관리",
    mentor_id: "m1",
    instructor_id: null,
    linked_profile: { name: "김멘토", display_name: "멘토K" },
    contract_file: { id: "f1", file_name: "멘토 계약서.pdf", file_size: 186_000, created_at: "2026-08-28T01:00:00Z" },
    signed_contract_file: {
      id: "f9",
      file_name: "멘토 계약서_서명.pdf",
      file_size: 190_000,
      created_at: "2026-08-30T01:00:00Z",
    },
    created_at: "2026-08-28T01:00:00Z",
    updated_at: null,
    ...extra,
  };
}

const ACTIVE = contract("k1");
const DRAFT = contract("k2", {
  status: "DRAFT",
  contractor_name: "박새멘토",
  title: "12기 데이터 멘토 계약",
  mentor_id: null,
  linked_profile: null,
  contract_file: null,
  signed_contract_file: null,
});
const VENDOR = contract("k3", {
  contract_type: "SW",
  cohort_id: null,
  cohort_number: null,
  settlement_type: "FIXED",
  total_amount: 1_200_000,
  unit_price: null,
  price_unit: null,
  vat_type: "EXCLUDED",
  no_show_pay_amount: null,
  mentoring_time_basis: null,
  status: "IN_PROGRESS",
  contractor_name: "줌코리아",
  contractor_phone: null,
  contractor_email: null,
  business_registration_number: "1234567890",
  contact_person_name: "최대리",
  title: "백엔드 과정 Zoom 라이선스",
  mentor_id: null,
  linked_profile: null,
  manager_name: "이매니저",
});
const AMENDMENT: Amendment = {
  id: "a1",
  contract_id: "k1",
  amended_on: "2026-11-20",
  reason: "운영 범위 확대",
  before: { unit_price: 45000 },
  after: { unit_price: 50000 },
  contract_file: null,
  created_by_user_id: "u1",
  created_by_name: "김관리",
  created_at: "2026-11-20T01:00:00Z",
};

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
];

function access(codes = ["educator.contract.read", "educator.contract.manage", "educator.mentor.read"]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: COHORTS,
  };
}

function mockApi({ codes }: { codes?: string[] } = {}) {
  const calls: { path: string; body: unknown }[] = [];
  const all = [ACTIVE, DRAFT, VENDOR];
  const byId = (id: unknown) => all.find((c) => c.id === id) ?? ACTIVE;
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes))),
    http.get(apiUrl("/api/v1/admin/contracts"), ({ request }) => {
      const p = new URL(request.url).searchParams;
      calls.push({ path: "list", body: p.toString() });
      const types = p.getAll("contract_type");
      const items = all.filter((c) => !types.length || types.includes(c.contract_type));
      return HttpResponse.json({
        items,
        total: items.length,
        limit: 20,
        offset: 0,
        counts: { MENTOR: 2, INSTRUCTOR: 0, SW: 1, EQUIPMENT: 0, OTHER: 0 },
      });
    }),
    http.get(apiUrl("/api/v1/admin/contracts/manager-candidates"), () => HttpResponse.json(MANAGERS)),
    http.get(apiUrl("/api/v1/admin/contracts/{contract_id}"), ({ params }) =>
      HttpResponse.json(byId(params.contract_id)),
    ),
    http.get(apiUrl("/api/v1/admin/contracts/{contract_id}/amendments"), ({ params }) =>
      HttpResponse.json(params.contract_id === "k1" ? [AMENDMENT] : []),
    ),
    http.post(apiUrl("/api/v1/admin/contracts/{contract_id}/progress"), async ({ request, params }) => {
      const text = await request.text();
      calls.push({ path: "progress", body: { id: params.contract_id, ...(text ? JSON.parse(text) : {}) } });
      return HttpResponse.json({ ...byId(params.contract_id), status: "IN_PROGRESS" });
    }),
    http.post(apiUrl("/api/v1/admin/contracts/{contract_id}/sign"), async ({ request, params }) => {
      calls.push({ path: "sign", body: { id: params.contract_id, ...((await request.json()) as object) } });
      return HttpResponse.json({ ...byId(params.contract_id), status: "ACTIVE" });
    }),
    http.post(apiUrl("/api/v1/admin/contract-files/uploads"), () =>
      HttpResponse.json({
        upload_id: "up1",
        url: "http://s3.test/contracts",
        fields: {},
        expires_at: "2026-11-27T02:00:00Z",
      }),
    ),
    http.post("http://s3.test/contracts", () => new HttpResponse(null, { status: 204 })),
    http.post(apiUrl("/api/v1/admin/contract-files/uploads/{upload_id}/confirm"), () =>
      HttpResponse.json({ id: "f-new", file_name: "서명.pdf", file_size: 1200, created_at: "2026-11-27T01:00:00Z" }),
    ),
    http.post(apiUrl("/api/v1/admin/contracts/{contract_id}/cancel"), async ({ request, params }) => {
      calls.push({ path: "cancel", body: await request.json() });
      return HttpResponse.json({ ...byId(params.contract_id), status: "CANCELED" });
    }),
    http.post(apiUrl("/api/v1/admin/contracts/{contract_id}/terminate"), async ({ request, params }) => {
      calls.push({ path: "terminate", body: await request.json() });
      return HttpResponse.json({ ...byId(params.contract_id), status: "TERMINATED" });
    }),
    http.post(apiUrl("/api/v1/admin/contracts/{contract_id}/amendments"), async ({ request }) => {
      calls.push({ path: "amend", body: await request.json() });
      return HttpResponse.json(AMENDMENT, { status: 201 });
    }),
    http.patch(apiUrl("/api/v1/admin/contracts/{contract_id}"), async ({ request, params }) => {
      const body = await request.json();
      calls.push({ path: "update", body });
      return HttpResponse.json({ ...byId(params.contract_id), ...(body as object) });
    }),
    http.delete(apiUrl("/api/v1/admin/contracts/{contract_id}"), ({ params }) => {
      calls.push({ path: "delete", body: params.contract_id });
      return new HttpResponse(null, { status: 204 });
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
    http.get(apiUrl("/api/v1/admin/approvals"), () => HttpResponse.json({ items: [], total: 0, limit: 1, offset: 0 })),
  );
  return calls;
}

beforeEach(() => {
  resetAuth();
  mockSignedIn(ADMIN);
  try {
    localStorage.clear();
  } catch {
    // 저장소가 없어도 이어 간다
  }
});

describe("행정 업무 > 계약 목록 (F96)", () => {
  it("처음엔 진행 중인 첫 기수 + 과정 공통, 종류 탭 건수·표 칸, 진행 중인 계약 상태로 불러온다", async () => {
    const calls = mockApi();
    const { router } = await renderRoute("/admin/administration/contracts");
    await waitFor(() => expect(router.state.location.search).toEqual({ cohort: "c12" }));
    const table = await screen.findByRole("table", { name: "계약" });
    const list = calls.filter((c) => c.path === "list").at(-1)?.body as string;
    expect(list).toContain("cohort_id=c12");
    expect(list).toContain("include_bootcamp_common=true");
    expect(new URLSearchParams(list).getAll("status")).toEqual(["DRAFT", "IN_PROGRESS", "SIGNED", "ACTIVE"]);
    expect(screen.getByRole("button", { name: "과정 / 기수" })).toHaveTextContent("백엔드 부트캠프 12기");
    // 상단 선택기와 겹치는 머리 칩·건수는 두지 않는다 (F96 보완)
    expect(screen.queryByText(/^계약 \d+건$/)).not.toBeInTheDocument();
    const tabs = screen.getByRole("navigation", { name: "계약 종류" });
    expect(within(tabs).getByRole("link", { name: "전체 3" })).toHaveAttribute("aria-current", "page");
    expect(within(tabs).getByRole("link", { name: "멘토 2" })).toBeInTheDocument();
    expect(within(tabs).getByRole("link", { name: "SW 1" })).toBeInTheDocument();
    expect(
      within(table)
        .getAllByRole("row")
        .slice(1)
        .map((r) =>
          within(r)
            .getAllByRole("cell")
            .map((c) => c.textContent),
        )[2],
    ).toEqual([
      "백엔드 과정 Zoom 라이선스",
      "SW",
      "줌코리아담당 최대리",
      "백엔드 부트캠프 / 공통",
      "2026.09.01 ~ 2027.02.28",
      "정액 1,200,000원부가세 별도",
      "진행 중",
      "이매니저",
    ]);
  });

  it("종류 탭·상태 묶음을 바꾸면 요청이 바뀌고, 상단에서 '과정 전체'를 고르면 과정으로 거른다", async () => {
    const calls = mockApi();
    const { router } = await renderRoute("/admin/administration/contracts?cohort=c12");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("link", { name: "SW 1" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ cohort: "c12", type: "SW" }));
    await waitFor(() => expect(calls.at(-1)?.body).toContain("contract_type=SW"));
    await user.click(screen.getByRole("combobox", { name: "상태" }));
    await user.click(await screen.findByRole("option", { name: "끝난 계약" }));
    await waitFor(() =>
      expect(new URLSearchParams(calls.at(-1)?.body as string).getAll("status")).toEqual([
        "ENDED",
        "TERMINATED",
        "CANCELED",
      ]),
    );
    await user.click(screen.getByRole("button", { name: "과정 / 기수" }));
    const popover = await screen.findByRole("dialog", { name: "기수 고르기" });
    await user.click(within(popover).getByRole("button", { name: "백엔드 부트캠프 과정 전체" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ bootcamp: "b1" }));
    await waitFor(() => expect(calls.at(-1)?.body).toContain("bootcamp_id=b1"));
    expect(localStorage.getItem("oz.admin.current-cohort")).toBeNull();
  });

  it("조회 권한만 있으면 [계약 추가]와 패널의 작업 버튼이 없다", async () => {
    mockApi({ codes: ["educator.contract.read"] });
    await renderRoute("/admin/administration/contracts?cohort=c12&contract=k1");
    const sheet = await screen.findByRole("dialog", { name: "12기 백엔드 멘토 계약" });
    expect(screen.queryByRole("button", { name: "계약 추가" })).not.toBeInTheDocument();
    expect(within(sheet).queryByRole("button", { name: "변경 등록" })).not.toBeInTheDocument();
    expect(within(sheet).queryByRole("button", { name: "더보기" })).not.toBeInTheDocument();
    expect(within(sheet).queryByRole("button", { name: "변경" })).not.toBeInTheDocument();
  });
});

describe("계약 추가 위저드 (F96)", () => {
  it("기존 멘토를 골라 단계마다 검사하고, 초안으로 저장한다", async () => {
    const calls = mockApi();
    const { router } = await renderRoute("/admin/administration/contracts?cohort=c12&contract=new");
    const sheet = await screen.findByRole("dialog", { name: "계약 추가" });
    const user = userEvent.setup();
    expect(within(sheet).getByRole("list", { name: "단계" })).toHaveTextContent("종류·과정 / 기수");
    expect(within(sheet).getByRole("combobox", { name: "기수" })).toHaveTextContent("12기");
    await user.click(within(sheet).getByRole("button", { name: /다음/ }));
    expect(await within(sheet).findByText("계약 명칭을 적어 주세요")).toBeInTheDocument();
    await user.type(within(sheet).getByLabelText("계약 명칭"), "12기 백엔드 멘토 계약");
    await user.click(within(sheet).getByRole("button", { name: /다음/ }));
    // 2단계: 기존 멘토 고르기
    await user.click(within(sheet).getByRole("button", { name: /다음/ }));
    expect(await within(sheet).findByText("멘토를 골라 주세요")).toBeInTheDocument();
    await user.click(await within(sheet).findByRole("option", { name: /이멘토/ }));
    await user.click(within(sheet).getByRole("button", { name: /다음/ }));
    // 3단계: 멘토는 단가(시간당·회당)·노쇼·정산 시간
    expect(within(sheet).getByRole("radiogroup", { name: "단가 기준" })).toBeInTheDocument();
    expect(within(sheet).queryByRole("radiogroup", { name: "정산 유형" })).not.toBeInTheDocument();
    await user.type(within(sheet).getByLabelText("단가"), "50000");
    expect(within(sheet).getByLabelText("단가")).toHaveValue("50,000");
    await user.click(within(sheet).getByRole("button", { name: /다음/ }));
    // 4단계: 계약서 없이, 담당은 나
    expect(await within(sheet).findByRole("region", { name: "담당" })).toHaveTextContent("김관리");
    await user.click(within(sheet).getByRole("button", { name: /다음/ }));
    // 5단계: 확인 — 계약서가 없으면 진행 시작은 못 한다
    expect(within(sheet).getByRole("region", { name: "확인" })).toHaveTextContent("시간당 50,000원");
    expect(within(sheet).getByRole("button", { name: "진행 시작" })).toBeDisabled();
    await user.click(within(sheet).getByRole("button", { name: "초안으로 저장" }));
    await waitFor(() => expect(calls.find((c) => c.path === "create")).toBeTruthy());
    expect(calls.find((c) => c.path === "create")?.body).toMatchObject({
      contract_type: "MENTOR",
      bootcamp_id: "b1",
      cohort_id: "c12",
      title: "12기 백엔드 멘토 계약",
      mentor_id: "m2",
      contractor_name: "이멘토",
      contractor_phone: "01022225678",
      settlement_type: "UNIT_PRICE",
      unit_price: 50000,
      price_unit: "HOURLY",
      no_show_pay_amount: 0,
      mentoring_time_basis: "ACTUAL_DURATION",
      manager_employee_id: "e1",
      contract_file_id: null,
    });
    expect(calls.some((c) => c.path === "progress")).toBe(false);
    await waitFor(() => expect(router.state.location.search).toEqual({ cohort: "c12", contract: "k9" }));
  });

  it("업체 계약(SW)은 업체명·사업자번호를 받고, 정액이면 계약 금액이 필요하다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/administration/contracts?cohort=c12&contract=new");
    const sheet = await screen.findByRole("dialog", { name: "계약 추가" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("radio", { name: "SW" }));
    await user.click(within(sheet).getByRole("combobox", { name: "기수" }));
    await user.click(await screen.findByRole("option", { name: "과정 공통" }));
    await user.type(within(sheet).getByLabelText("계약 명칭"), "Zoom 라이선스");
    await user.click(within(sheet).getByRole("button", { name: /다음/ }));
    await user.type(within(sheet).getByLabelText("업체명"), "줌코리아");
    await user.type(within(sheet).getByLabelText("사업자번호"), "123");
    await user.click(within(sheet).getByRole("button", { name: /다음/ }));
    expect(await within(sheet).findByText("사업자등록번호는 숫자 10자리예요")).toBeInTheDocument();
    await user.clear(within(sheet).getByLabelText("사업자번호"));
    await user.type(within(sheet).getByLabelText("사업자번호"), "123-45-67890");
    await user.click(within(sheet).getByRole("button", { name: /다음/ }));
    await user.click(within(sheet).getByRole("radio", { name: "정액" }));
    await user.click(within(sheet).getByRole("button", { name: /다음/ }));
    expect(await within(sheet).findByText("계약 금액을 적어 주세요")).toBeInTheDocument();
    await user.type(within(sheet).getByLabelText("계약 금액"), "1200000");
    await user.click(within(sheet).getByRole("radio", { name: "별도" }));
    await user.click(within(sheet).getByRole("button", { name: /다음/ }));
    await user.click(within(sheet).getByRole("button", { name: /다음/ }));
    await user.click(within(sheet).getByRole("button", { name: "초안으로 저장" }));
    await waitFor(() => expect(calls.find((c) => c.path === "create")).toBeTruthy());
    expect(calls.find((c) => c.path === "create")?.body).toMatchObject({
      contract_type: "SW",
      cohort_id: null,
      contractor_name: "줌코리아",
      contractor_phone: null,
      business_registration_number: "1234567890",
      settlement_type: "FIXED",
      total_amount: 1_200_000,
      unit_price: null,
      price_unit: null,
      vat_type: "EXCLUDED",
      no_show_pay_amount: null,
      mentoring_time_basis: null,
      mentor_id: null,
    });
  });
});

describe("계약 패널 (F96)", () => {
  it("이행 중: 상태 단계·금액·이름·변경 이력, [변경 등록]은 바뀐 항목과 사유를 보낸다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/administration/contracts?cohort=c12&contract=k1");
    const sheet = await screen.findByRole("dialog", { name: "12기 백엔드 멘토 계약" });
    const flow = within(sheet).getByRole("list", { name: "계약 단계" });
    expect(within(flow).getAllByRole("listitem")[3]).toHaveAttribute("aria-current", "step");
    expect(within(sheet).getByRole("region", { name: "금액" })).toHaveTextContent("단가 · 시간당50,000원");
    expect(within(sheet).getByRole("region", { name: "이름 또는 업체명" })).toHaveTextContent("010-****-1234");
    const history = await within(sheet).findByRole("list", { name: "변경 이력" });
    expect(history).toHaveTextContent("단가45,000원→50,000원");
    expect(history).toHaveTextContent("사유: 운영 범위 확대");
    // 종료일이 있으면 다음 단계 버튼이 없다
    expect(within(sheet).queryByRole("button", { name: "종료" })).not.toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "변경 등록" }));
    const form = await screen.findByRole("form", { name: "변경 등록" });
    expect(within(form).queryByLabelText("이름")).not.toBeInTheDocument();
    await user.clear(within(form).getByLabelText("단가"));
    await user.type(within(form).getByLabelText("단가"), "55000");
    await user.click(within(form).getByRole("button", { name: "변경 등록" }));
    expect(await within(form).findByText("변경 사유를 적어 주세요.")).toBeInTheDocument();
    await user.type(within(form).getByLabelText("사유"), "단가 인상");
    await user.click(within(form).getByRole("button", { name: "변경 등록" }));
    await waitFor(() => expect(calls.find((c) => c.path === "amend")).toBeTruthy());
    expect(calls.find((c) => c.path === "amend")?.body).toMatchObject({
      reason: "단가 인상",
      changes: { unit_price: 55000 },
      contract_file_id: null,
    });
  });

  it("해지는 ⋯ 메뉴에서 사유를 골라 확인한다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/administration/contracts?cohort=c12&contract=k1");
    const sheet = await screen.findByRole("dialog", { name: "12기 백엔드 멘토 계약" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "더보기" }));
    expect(screen.queryByRole("menuitem", { name: "취소" })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("menuitem", { name: "해지" }));
    const dialog = await screen.findByRole("dialog", { name: "계약을 해지할까요?" });
    await user.click(within(dialog).getByRole("radio", { name: "귀책 사유" }));
    await user.type(within(dialog).getByLabelText("상세 (선택)"), "연락 두절");
    await user.click(within(dialog).getByRole("button", { name: "해지" }));
    await waitFor(() => expect(calls.find((c) => c.path === "terminate")).toBeTruthy());
    expect(calls.find((c) => c.path === "terminate")?.body).toMatchObject({
      reason: "TERMINATED_BY_FAULT",
      detail: "연락 두절",
    });
  });

  it("멘토 없는 새 사람 초안도 [수정]에서 저장된다 (A115)", async () => {
    const calls = mockApi();
    await renderRoute("/admin/administration/contracts?cohort=c12&contract=k2");
    const sheet = await screen.findByRole("dialog", { name: "12기 데이터 멘토 계약" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "수정" }));
    const form = await screen.findByRole("form", { name: "계약 수정" });
    await user.type(within(form).getByLabelText("계약 명칭"), " 2");
    await user.click(within(form).getByRole("button", { name: "저장" }));
    await waitFor(() => expect(calls.find((c) => c.path === "update")).toBeTruthy());
    expect(calls.find((c) => c.path === "update")?.body).toEqual({ title: "12기 데이터 멘토 계약 2" });
  });

  it("초안: [진행]은 계약서 원본을 올려야 하고, ⋯에서 취소(사유 필수)·삭제", async () => {
    const calls = mockApi();
    await renderRoute("/admin/administration/contracts?cohort=c12&contract=k2");
    const sheet = await screen.findByRole("dialog", { name: "12기 데이터 멘토 계약" });
    const user = userEvent.setup();
    expect(within(sheet).getByRole("button", { name: "수정" })).toBeInTheDocument();
    // 새 사람의 멘토 계약은 계약 완료 때 멘토가 정해진다 (A115)
    expect(within(sheet).getByText("계약 완료 때 연결")).toBeInTheDocument();
    expect(within(sheet).queryByRole("link", { name: "멘토 보기" })).not.toBeInTheDocument();
    await user.click(within(sheet).getByRole("button", { name: "진행" }));
    const step = await screen.findByRole("dialog", { name: "계약을 진행할까요?" });
    await user.click(within(step).getByRole("button", { name: "진행" }));
    expect(await within(step).findByText("계약서 원본을 올려 주세요.")).toBeInTheDocument();
    await user.upload(
      within(step).getByLabelText("계약서 원본 (서명 전)"),
      new File(["%PDF"], "원본.pdf", { type: "application/pdf" }),
    );
    expect(await within(step).findByText(/서명.pdf/)).toBeInTheDocument();
    await user.click(within(step).getByRole("button", { name: "진행" }));
    await waitFor(() => expect(calls.find((c) => c.path === "progress")).toBeTruthy());
    expect(calls.find((c) => c.path === "progress")?.body).toEqual({ id: "k2", contract_file_id: "f-new" });

    await user.click(within(sheet).getByRole("button", { name: "더보기" }));
    await user.click(await screen.findByRole("menuitem", { name: "취소" }));
    const cancel = await screen.findByRole("dialog", { name: "계약을 취소할까요?" });
    await user.click(within(cancel).getByRole("button", { name: "취소하기" }));
    expect(await within(cancel).findByText("취소 사유를 적어 주세요.")).toBeInTheDocument();
    await user.type(within(cancel).getByLabelText("취소 사유"), "조건 불일치");
    await user.click(within(cancel).getByRole("button", { name: "취소하기" }));
    await waitFor(() => expect(calls.find((c) => c.path === "cancel")).toBeTruthy());
    expect(calls.find((c) => c.path === "cancel")?.body).toMatchObject({ reason: "조건 불일치" });
  });

  it("진행 중 업체 계약: [계약 완료]와 [수정]에서 바뀐 항목만 보낸다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/administration/contracts?cohort=c12&contract=k3");
    const sheet = await screen.findByRole("dialog", { name: "백엔드 과정 Zoom 라이선스" });
    expect(within(sheet).getByRole("region", { name: "이름 또는 업체명" })).toHaveTextContent("1234567890");
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "수정" }));
    const form = await screen.findByRole("form", { name: "계약 수정" });
    await user.type(within(form).getByLabelText("담당자"), "님");
    await user.click(within(form).getByRole("button", { name: "저장" }));
    await waitFor(() => expect(calls.find((c) => c.path === "update")).toBeTruthy());
    expect(calls.find((c) => c.path === "update")?.body).toEqual({ contact_person_name: "최대리님" });
    const again = await screen.findByRole("dialog", { name: "백엔드 과정 Zoom 라이선스" });
    await user.click(within(again).getByRole("button", { name: "계약 완료" }));
    const step = await screen.findByRole("dialog", { name: "계약 완료로 바꿀까요?" });
    await user.click(within(step).getByRole("button", { name: "계약 완료" }));
    expect(await within(step).findByText("서명된 계약서를 올려 주세요.")).toBeInTheDocument();
    await user.upload(
      within(step).getByLabelText("서명된 계약서"),
      new File(["%PDF"], "서명.pdf", { type: "application/pdf" }),
    );
    await user.click(within(step).getByRole("button", { name: "계약 완료" }));
    await waitFor(() => expect(calls.find((c) => c.path === "sign")).toBeTruthy());
    expect(calls.find((c) => c.path === "sign")?.body).toEqual({ id: "k3", signed_contract_file_id: "f-new" });
  });
});
