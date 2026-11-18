import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { StaffRegistration } from "./staff-api";
import { makeMe, mockSignedIn, resetAuth } from "./test-utils";

const STAFF = makeMe({
  name: "임운영",
  email: "staff@nextrunners.co.kr",
  account_type: "STAFF",
  approval_status: "PENDING",
  approved_at: null,
  roles: [],
});

const OPTIONS = {
  departments: [
    { id: "d1", parent_id: null, name: "교육본부" },
    { id: "d2", parent_id: "d1", name: "교육운영팀" },
  ],
  positions: [{ id: "p1", name: "매니저" }],
  employment_types: ["REGULAR", "CONTRACT"],
  staff_roles: ["MANAGER", "ASSISTANT"],
  bootcamps: [{ id: "b1", name: "백엔드 부트캠프", code: "BE" }],
  cohorts: [
    {
      id: "c9",
      bootcamp_id: "b1",
      cohort_number: 9,
      status: "ONGOING",
      start_date: "2026-01-01",
      end_date: "2026-06-30",
    },
  ],
};

function registration(overrides: Partial<StaffRegistration> = {}): StaffRegistration {
  return {
    id: "r1",
    status: "PENDING",
    department_id: "d2",
    position_id: "p1",
    employment_type: "REGULAR",
    assignments: [{ role: "MANAGER", bootcamp_id: "b1", cohort_id: null }],
    reviewed_at: null,
    reject_reason: null,
    created_at: "2026-11-16T01:24:00Z",
    ...overrides,
  };
}

function mockStaff(mine: StaffRegistration | null) {
  let current = mine;
  const puts: unknown[] = [];
  mockSignedIn(STAFF);
  server.use(
    http.get(apiUrl("/api/v1/me/staff-registration/options"), () => HttpResponse.json(OPTIONS)),
    http.get(apiUrl("/api/v1/me/staff-registration"), () => HttpResponse.json(current)),
    http.put(apiUrl("/api/v1/me/staff-registration"), async ({ request }) => {
      const body = (await request.json()) as Partial<StaffRegistration>;
      puts.push(body);
      current = registration({ ...body, status: "PENDING" });
      return HttpResponse.json(current);
    }),
  );
  return puts;
}

beforeEach(() => resetAuth());

async function pick(user: ReturnType<typeof userEvent.setup>, combobox: HTMLElement, option: RegExp | string) {
  await user.click(combobox);
  await user.click(await screen.findByRole("option", { name: option }));
}

describe("운영진 로그인", () => {
  it("Google 로그인 실패 사유를 안내한다", async () => {
    await renderRoute("/staff/login?error=google_domain_not_allowed");
    expect(await screen.findByRole("alert")).toHaveTextContent("회사 Google 계정으로만 로그인할 수 있어요");
    expect(screen.getByRole("button", { name: "Google 계정으로 로그인" })).toBeInTheDocument();
  });

  it("취소는 오류가 아니라 안내로 보여 준다", async () => {
    await renderRoute("/staff/login?error=google_login_cancelled");
    expect(await screen.findByRole("status")).toHaveTextContent("Google 로그인을 취소했어요");
  });

  it("수강생·멘토 로그인 화면과 서로 오간다", async () => {
    const user = userEvent.setup();
    const { router } = await renderRoute("/login");
    await user.click(await screen.findByRole("link", { name: "운영진 로그인" }));
    await screen.findByRole("heading", { name: "운영진 로그인" });
    expect(router.state.location.pathname).toBe("/staff/login");
  });
});

describe("운영진 최초 정보 입력", () => {
  it("승인 전 운영진은 정보 입력 화면으로 가고, 담당 없이도 신청하면 승인 대기가 된다", async () => {
    const puts = mockStaff(null);
    const user = userEvent.setup();
    const { router } = await renderRoute("/");
    await screen.findByRole("heading", { name: "운영진 정보 입력" });
    expect(router.state.location.pathname).toBe("/staff/registration");
    expect(screen.getByText(/담당 없이 신청할 수 있어요/)).toBeInTheDocument();

    await pick(user, screen.getByRole("combobox", { name: "부서" }), "교육본부 › 교육운영팀");
    await pick(user, screen.getByRole("combobox", { name: "직위" }), "매니저");
    await pick(user, screen.getByRole("combobox", { name: "고용 형태" }), "정규직");
    await user.click(screen.getByRole("button", { name: "승인 신청" }));

    expect(await screen.findByRole("heading", { name: "승인을 기다리고 있어요" })).toBeInTheDocument();
    expect(puts).toEqual([{ department_id: "d2", position_id: "p1", employment_type: "REGULAR", assignments: [] }]);
  });

  it("담당을 고르면 과정 전체·기수를 API 형식으로 보내고, 조교는 기수만 고를 수 있다", async () => {
    const puts = mockStaff(null);
    const user = userEvent.setup();
    await renderRoute("/staff/registration");
    await pick(user, await screen.findByRole("combobox", { name: "부서" }), "교육본부 › 교육운영팀");
    await pick(user, screen.getByRole("combobox", { name: "직위" }), "매니저");
    await pick(user, screen.getByRole("combobox", { name: "고용 형태" }), "정규직");
    await user.click(screen.getByRole("button", { name: "담당 추가" }));
    await pick(user, screen.getByRole("combobox", { name: "담당 1 대상" }), "백엔드 부트캠프 (과정 전체)");
    await user.click(screen.getByRole("button", { name: "담당 추가" }));
    await pick(user, screen.getByRole("combobox", { name: "담당 2 역할" }), "조교");
    await user.click(screen.getByRole("combobox", { name: "담당 2 대상" }));
    const listbox = await screen.findByRole("listbox");
    expect(within(listbox).queryByRole("option", { name: /과정 전체/ })).not.toBeInTheDocument();
    await user.click(within(listbox).getByRole("option", { name: "백엔드 부트캠프 9기" }));
    await user.click(screen.getByRole("button", { name: "승인 신청" }));

    await screen.findByRole("heading", { name: "승인을 기다리고 있어요" });
    expect(puts[0]).toMatchObject({
      assignments: [
        { role: "MANAGER", bootcamp_id: "b1", cohort_id: null },
        { role: "ASSISTANT", bootcamp_id: null, cohort_id: "c9" },
      ],
    });
  });

  it("승인 대기에서 새로고침했는데 승인됐으면 운영진 홈으로 간다", async () => {
    mockStaff(registration());
    const user = userEvent.setup();
    const { router } = await renderRoute("/staff/registration");
    expect(await screen.findByText("교육본부 › 교육운영팀")).toBeInTheDocument();
    expect(screen.getByText("백엔드 부트캠프 (과정 전체)")).toBeInTheDocument();
    server.use(
      http.get(apiUrl("/api/v1/me"), () =>
        HttpResponse.json({
          ...STAFF,
          approval_status: "APPROVED",
          approved_at: "2026-11-17T00:00:00Z",
          roles: [{ role: "COHORT_MANAGER", scope_type: "BOOTCAMP", scope_id: "b1", expires_at: null }],
        }),
      ),
    );
    await user.click(screen.getByRole("button", { name: "새로고침" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/admin"));
    expect(await screen.findByText("운영 매니저")).toBeInTheDocument();
  });

  it("반려되면 사유를 보여 주고 이전 입력을 채운 폼으로 다시 신청한다", async () => {
    mockStaff(
      registration({
        status: "REJECTED",
        reject_reason: "담당 기수를 다시 확인해 주세요.",
        reviewed_at: "2026-11-16T06:02:00Z",
      }),
    );
    const user = userEvent.setup();
    await renderRoute("/staff/registration");
    expect(await screen.findByRole("alert")).toHaveTextContent("담당 기수를 다시 확인해 주세요.");
    await user.click(screen.getByRole("button", { name: "고쳐서 다시 신청" }));
    expect(await screen.findByRole("combobox", { name: "부서" })).toHaveTextContent("교육본부 › 교육운영팀");
    expect(screen.getByRole("combobox", { name: "담당 1 대상" })).toHaveTextContent("백엔드 부트캠프 (과정 전체)");
  });
});
