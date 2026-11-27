import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { Applicant, Candidates, StudentCandidate } from "./api";
import { matchLabel, matchTag } from "./labels";

const ADMIN = makeMe({
  name: "김운영",
  email: "staff@nextrunners.co.kr",
  account_type: "STAFF",
  is_super_admin: true,
});

const ACCESS: StaffAccess = {
  is_super_admin: false,
  position: null,
  permissions: [
    { code: "member.approval.read", is_global: true, bootcamp_ids: [], cohort_ids: [] },
    { code: "member.approval.manage", is_global: true, bootcamp_ids: [], cohort_ids: [] },
    { code: "educator.contract.read", is_global: true, bootcamp_ids: [], cohort_ids: [] },
    { code: "educator.contract.manage", is_global: true, bootcamp_ids: [], cohort_ids: [] },
  ],
  cohorts: [
    {
      id: "c12",
      bootcamp_id: "b1",
      bootcamp_name: "백엔드",
      cohort_number: 12,
      start_date: "2026-11-01",
      end_date: "2027-04-30",
      status: "ONGOING",
    },
  ],
};

function applicant(
  overrides: Partial<Applicant> & { type?: "STUDENT" | "MENTOR"; match?: Applicant["signup"]["match_result"] } = {},
): Applicant {
  const { type = "STUDENT", match = "NO_MATCH", ...rest } = overrides;
  return {
    user_id: "u1",
    name: "가수강",
    email: "student@example.com",
    phone_number: "01012341234",
    approval_status: "PENDING",
    signup: {
      id: "sg1",
      signup_type: type,
      status: "PENDING",
      requested_cohort_id: type === "STUDENT" ? "c12" : null,
      nickname: null,
      display_name_preference: null,
      match_result: match,
      reject_reason: null,
      reviewed_at: null,
      created_at: "2026-11-16T01:00:00Z",
    },
    requested_bootcamp_name: type === "STUDENT" ? "백엔드" : null,
    requested_cohort_number: type === "STUDENT" ? 12 : null,
    ...rest,
  };
}

function student(overrides: Partial<StudentCandidate>): StudentCandidate {
  return {
    student_id: "st1",
    name: "가수강",
    phone_number: "01012341234",
    cohort_id: "c12",
    bootcamp_name: "백엔드",
    cohort_number: 12,
    enrollment_status: "ENROLLED",
    name_match: true,
    phone_match: true,
    same_cohort: true,
    ...overrides,
  };
}

const MENTOR_APPLICANT = applicant({ user_id: "u2", name: "김멘토", email: "mentor@example.com", type: "MENTOR" });

function mockApprovals({ students = [applicant()], mentors = [MENTOR_APPLICANT] } = {}) {
  const calls = {
    approve: [] as unknown[],
    reject: [] as unknown[],
    candidates: [] as (string | null)[],
    cohort: [] as (string | null)[],
  };
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(ACCESS)),
    http.get(apiUrl("/api/v1/admin/approvals"), ({ request }) => {
      const p = new URL(request.url).searchParams;
      const type = p.get("signup_type");
      calls.cohort.push(p.get("cohort_id"));
      const items = type === "MENTOR" ? mentors : type === "STUDENT" ? students : [...students, ...mentors];
      return HttpResponse.json({ items, total: items.length, limit: 20, offset: 0 });
    }),
    http.get(apiUrl("/api/v1/admin/approvals/{user_id}/candidates"), ({ request, params }) => {
      const q = new URL(request.url).searchParams.get("q");
      calls.candidates.push(q);
      const body: Candidates =
        params.user_id === "u2"
          ? {
              signup_type: "MENTOR",
              students: [],
              mentors: [
                {
                  mentor_id: "pm1",
                  name: "김멘토",
                  phone_number: "01077778888",
                  contract_count: 2,
                  name_match: true,
                  phone_match: true,
                },
              ],
              contracts: [
                {
                  contract_id: "ct1",
                  contractor_name: "김멘토",
                  contractor_phone: "01077778888",
                  title: "2026 멘토 계약",
                  status: "ACTIVE",
                  start_date: "2026-07-01",
                  end_date: "2026-12-31",
                  name_match: true,
                  phone_match: true,
                },
              ],
            }
          : {
              signup_type: "STUDENT",
              contracts: [],
              mentors: [],
              students: q
                ? [student({ student_id: "st9", name: "나수강", name_match: false, phone_match: false })]
                : [
                    student({ student_id: "st1" }),
                    student({ student_id: "st2", cohort_id: "c13", cohort_number: 13, same_cohort: false }),
                  ],
            };
      return HttpResponse.json(body);
    }),
    http.post(apiUrl("/api/v1/admin/approvals/{user_id}/approve"), async ({ request, params }) => {
      const body = await request.json();
      calls.approve.push({ user: params.user_id, ...(body as object) });
      if ((body as { student_id?: string }).student_id === "st9")
        return HttpResponse.json(errorBody("student_already_claimed"), { status: 422 });
      return HttpResponse.json({ ...applicant(), approval_status: "APPROVED" });
    }),
    http.post(apiUrl("/api/v1/admin/approvals/{user_id}/reject"), async ({ request }) => {
      calls.reject.push(await request.json());
      return HttpResponse.json(applicant());
    }),
  );
  return calls;
}

describe("가입 승인 표시 (A31·A82)", () => {
  it("자동 매칭·일치 태그", () => {
    expect(matchLabel(applicant()).label).toBe("명단 없음");
    expect(matchLabel(applicant({ match: "AMBIGUOUS" })).label).toBe("후보 여러 명");
    expect(matchLabel(MENTOR_APPLICANT).label).toBe("가입 전 멘토 없음");
    expect(matchTag({ name_match: true, phone_match: true })).toBe("이름·휴대폰 일치");
    expect(matchTag({ name_match: true, phone_match: false })).toBe("휴대폰 다름");
    expect(matchTag({ name_match: false, phone_match: true })).toBe("이름 다름");
  });
});

describe("회원 가입 승인 (FE-15a)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("메뉴·탭 건수·표를 보여 주고 기수로 거른다", async () => {
    const calls = mockApprovals();
    const { router } = await renderRoute("/admin/members/approvals");
    expect(await screen.findByRole("heading", { name: "가입 승인", level: 1 })).toBeInTheDocument();
    const menu = screen.getByRole("navigation", { name: "메뉴" });
    expect(await within(menu).findByRole("link", { name: /가입 승인\s*대기\s*2/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
    const tabs = screen.getByRole("navigation", { name: "가입 유형" });
    expect(await within(tabs).findByRole("link", { name: "수강생 1" })).toHaveAttribute("aria-current", "page");
    expect(within(tabs).getByRole("link", { name: "멘토·강사 1" })).toHaveAttribute(
      "href",
      "/admin/members/approvals?tab=mentor",
    );
    expect(within(tabs).queryByRole("link", { name: /운영진/ })).not.toBeInTheDocument(); // 운영진 승인 권한 없음
    const row = within(screen.getByRole("table")).getByRole("row", { name: /가수강/ });
    expect(row).toHaveTextContent("010-****-1234");
    expect(row).toHaveTextContent("백엔드 12기");
    expect(row).toHaveTextContent("명단 없음");
    expect(row).toHaveTextContent("11/16");

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "기수" }));
    const popover = await screen.findByRole("dialog", { name: "기수 고르기" });
    expect(within(popover).getByRole("button", { name: "전체 기수" })).toHaveAttribute("aria-pressed", "true");
    await user.click(within(popover).getByRole("button", { name: "백엔드 12기" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ cohort: "c12" }));
    await waitFor(() => expect(calls.cohort).toContain("c12"));
  });

  it("수강생 승인: 후보를 고르면 다른 기수 경고, 검색, 연결하고 승인", async () => {
    const calls = mockApprovals();
    await renderRoute("/admin/members/approvals");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "가수강 승인" }));
    const dialog = await screen.findByRole("dialog", { name: "가입 승인 · 가수강" });
    expect(dialog).toHaveTextContent("신청 기수는 백엔드 12기예요");
    const submit = within(dialog).getByRole("button", { name: "연결하고 승인" });
    expect(submit).toBeDisabled();
    await user.click(await within(dialog).findByRole("radio", { name: "가수강 백엔드 13기" }));
    expect(within(dialog).getByText("다른 기수의 명단이에요")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("radio", { name: "가수강 백엔드 12기" }));
    expect(within(dialog).queryByText("다른 기수의 명단이에요")).not.toBeInTheDocument();

    await user.type(within(dialog).getByRole("textbox", { name: "후보 검색" }), "나수");
    await user.click(await within(dialog).findByRole("radio", { name: "나수강 백엔드 12기" }));
    expect(within(dialog).getByText("이름이나 휴대폰이 달라요")).toBeInTheDocument();
    expect(calls.candidates).toContain("나수");
    await user.click(submit);
    expect(await within(dialog).findByText(/이미 다른 회원과 연결된 명단이에요/)).toBeInTheDocument();

    await user.clear(within(dialog).getByRole("textbox", { name: "후보 검색" }));
    await user.click(await within(dialog).findByRole("radio", { name: "가수강 백엔드 12기" }));
    await user.click(submit);
    await waitFor(() => expect(calls.approve.at(-1)).toEqual({ user: "u1", student_id: "st1" }));
    expect(await screen.findByText("가수강님 가입을 승인했어요")).toBeInTheDocument();
  });

  it("멘토 승인: 가입 전 멘토를 고르면 그 멘토에 연결, 고르지 않으면 새 멘토 (A105)", async () => {
    const calls = mockApprovals();
    await renderRoute("/admin/members/approvals?tab=mentor");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "김멘토 승인" }));
    const dialog = await screen.findByRole("dialog", { name: "가입 승인 · 김멘토" });
    expect(within(dialog).getByRole("button", { name: "새 멘토로 승인" })).toBeEnabled();
    const list = await within(dialog).findByRole("radiogroup", { name: "연결할 가입 전 멘토" });
    expect(list).toHaveTextContent("김멘토 · 010-****-8888계약 2건 · 이름·휴대폰 일치가입 전");
    await user.click(within(list).getByRole("radio", { name: "김멘토 연결" }));
    await user.click(within(dialog).getByRole("button", { name: "이 멘토에 연결하고 승인" }));
    await waitFor(() => expect(calls.approve.at(-1)).toEqual({ user: "u2", mentor_id: "pm1" }));
  });

  it("반려는 사유가 있어야 한다", async () => {
    const calls = mockApprovals();
    await renderRoute("/admin/members/approvals");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "가수강 반려" }));
    const dialog = await screen.findByRole("dialog", { name: "가입 반려 · 가수강" });
    const button = within(dialog).getByRole("button", { name: "반려" });
    expect(button).toBeDisabled();
    await user.type(within(dialog).getByRole("textbox", { name: "반려 사유" }), "명단에 없어요");
    await user.click(button);
    await waitFor(() => expect(calls.reject).toEqual([{ reason: "명단에 없어요" }]));
  });

  it("처리할 신청이 없으면 빈 상태, 권한이 없으면 메뉴가 없다", async () => {
    mockApprovals({ students: [], mentors: [] });
    await renderRoute("/admin/members/approvals");
    expect(await screen.findByRole("heading", { name: "처리할 가입 신청이 없어요" })).toBeInTheDocument();
  });
});
