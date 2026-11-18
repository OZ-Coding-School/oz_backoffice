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

const cohort = (id: string, bootcamp_id: string, cohort_number: number) => ({
  id,
  bootcamp_id,
  cohort_number,
  status: "ONGOING",
  start_date: "2026-01-01",
  end_date: "2026-06-30",
});

const OPTIONS = {
  departments: [
    { id: "d1", name: "교육운영본부" },
    { id: "d2", name: "경영지원본부" },
  ],
  teams: [
    { id: "t1", department_id: "d1", name: "교육 1팀" },
    { id: "t2", department_id: "d2", name: "인사팀" },
  ],
  positions: [
    { id: "p1", name: "운영 매니저", assignment_scope: "COURSE" },
    { id: "p2", name: "조교", assignment_scope: "COHORT" },
    { id: "p3", name: "인턴", assignment_scope: null },
  ],
  employment_types: ["REGULAR", "CONTRACT"],
  staff_roles: ["MANAGER", "ASSISTANT"],
  bootcamps: [
    { id: "b1", name: "백엔드 부트캠프", code: "BE", team_id: "t1" },
    { id: "b2", name: "프론트엔드 부트캠프", code: "FE", team_id: "t1" },
    { id: "b9", name: "다른 팀 과정", code: "XX", team_id: null },
  ],
  cohorts: [cohort("c9", "b1", 9), cohort("c10", "b1", 10), cohort("f3", "b2", 3)],
};

function registration(overrides: Partial<StaffRegistration> = {}): StaffRegistration {
  return {
    id: "r1",
    status: "PENDING",
    department_id: "d1",
    team_id: "t1",
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
  it("부서 → 팀 → 직위 순서로 칸이 나타나고, 부서 직속은 담당 없이 신청한다", async () => {
    const puts = mockStaff(null);
    const user = userEvent.setup();
    const { router } = await renderRoute("/");
    await screen.findByRole("heading", { name: "운영진 정보 입력" });
    expect(router.state.location.pathname).toBe("/staff/registration");
    expect(screen.queryByRole("combobox", { name: "팀" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "직위" })).not.toBeInTheDocument();

    await pick(user, screen.getByRole("combobox", { name: "부서" }), "교육운영본부");
    expect(screen.queryByRole("combobox", { name: "직위" })).not.toBeInTheDocument();
    await pick(user, screen.getByRole("combobox", { name: "팀" }), "선택 안 함 (부서 직속)");
    await pick(user, screen.getByRole("combobox", { name: "직위" }), "운영 매니저");
    await pick(user, screen.getByRole("combobox", { name: "고용 형태" }), "정규직");
    expect(screen.queryByText("담당 과정")).not.toBeInTheDocument(); // 팀이 없으면 고를 과정이 없다
    await user.click(screen.getByRole("button", { name: "승인 신청" }));

    expect(await screen.findByRole("heading", { name: "승인을 기다리고 있어요" })).toBeInTheDocument();
    expect(puts).toEqual([
      { department_id: "d1", team_id: null, position_id: "p1", employment_type: "REGULAR", assignments: [] },
    ]);
  });

  it("과정 담당 직위는 팀 과정을 드롭다운에서 추가·삭제하고, 직위를 바꾸면 담당이 비워지고 섹션이 사라진다", async () => {
    const puts = mockStaff(null);
    const user = userEvent.setup();
    await renderRoute("/staff/registration");
    await pick(user, await screen.findByRole("combobox", { name: "부서" }), "교육운영본부");
    await pick(user, screen.getByRole("combobox", { name: "팀" }), "교육 1팀");
    await pick(user, screen.getByRole("combobox", { name: "직위" }), "운영 매니저");
    await pick(user, screen.getByRole("combobox", { name: "고용 형태" }), "정규직");

    const add = () => screen.getByRole("combobox", { name: "담당 과정 추가" });
    await user.click(add());
    let listbox = await screen.findByRole("listbox");
    expect(
      within(listbox)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["백엔드 부트캠프", "프론트엔드 부트캠프"]); // 다른 팀 과정은 없다
    await user.click(within(listbox).getByRole("option", { name: "백엔드 부트캠프" }));
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
    await user.click(add());
    listbox = await screen.findByRole("listbox");
    expect(
      within(listbox)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["프론트엔드 부트캠프"]);
    await user.keyboard("{Escape}");

    await pick(user, screen.getByRole("combobox", { name: "직위" }), "인턴");
    expect(screen.queryByText("담당 과정")).not.toBeInTheDocument();
    await pick(user, screen.getByRole("combobox", { name: "직위" }), "운영 매니저");
    expect(screen.queryByRole("list", { name: "추가한 담당 과정" })).not.toBeInTheDocument();

    await pick(user, add(), "프론트엔드 부트캠프");
    await pick(user, add(), "백엔드 부트캠프");
    expect(add()).toHaveTextContent("모든 과정을 추가했어요");
    await user.click(screen.getByRole("button", { name: "프론트엔드 부트캠프 빼기" }));
    await pick(user, add(), "프론트엔드 부트캠프");
    await user.click(screen.getByRole("button", { name: "승인 신청" }));

    await screen.findByRole("heading", { name: "승인을 기다리고 있어요" });
    expect(puts[0]).toMatchObject({
      team_id: "t1",
      assignments: [
        { role: "MANAGER", bootcamp_id: "b1", cohort_id: null },
        { role: "MANAGER", bootcamp_id: "b2", cohort_id: null },
      ],
    });
  });

  it("조교는 과정을 고른 뒤 그 과정의 기수를 하나 고른다", async () => {
    const puts = mockStaff(null);
    const user = userEvent.setup();
    await renderRoute("/staff/registration");
    await pick(user, await screen.findByRole("combobox", { name: "부서" }), "교육운영본부");
    await pick(user, screen.getByRole("combobox", { name: "팀" }), "교육 1팀");
    await pick(user, screen.getByRole("combobox", { name: "직위" }), "조교");
    await pick(user, screen.getByRole("combobox", { name: "고용 형태" }), "정규직");

    expect(screen.queryByRole("combobox", { name: "기수" })).not.toBeInTheDocument();
    await pick(user, screen.getByRole("combobox", { name: "과정" }), "프론트엔드 부트캠프");
    await pick(user, screen.getByRole("combobox", { name: "기수" }), "3기");
    // 과정을 바꾸면 기수는 비운다
    await pick(user, screen.getByRole("combobox", { name: "과정" }), "백엔드 부트캠프");
    expect(screen.getByRole("combobox", { name: "기수" })).toHaveTextContent("기수를 선택하세요");
    await user.click(screen.getByRole("combobox", { name: "기수" }));
    const listbox = await screen.findByRole("listbox");
    expect(
      within(listbox)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["9기", "10기"]);
    await user.click(within(listbox).getByRole("option", { name: "10기" }));
    await user.click(screen.getByRole("button", { name: "승인 신청" }));

    await screen.findByRole("heading", { name: "승인을 기다리고 있어요" });
    expect(puts[0]).toMatchObject({
      position_id: "p2",
      assignments: [{ role: "ASSISTANT", bootcamp_id: null, cohort_id: "c10" }],
    });
  });

  it("부서를 바꾸면 팀부터 다시 고른다", async () => {
    mockStaff(null);
    const user = userEvent.setup();
    await renderRoute("/staff/registration");
    await pick(user, await screen.findByRole("combobox", { name: "부서" }), "교육운영본부");
    await pick(user, screen.getByRole("combobox", { name: "팀" }), "교육 1팀");
    expect(screen.getByRole("combobox", { name: "직위" })).toBeInTheDocument();

    await pick(user, screen.getByRole("combobox", { name: "부서" }), "경영지원본부");
    expect(screen.getByRole("combobox", { name: "팀" })).toHaveTextContent("팀을 선택하세요");
    expect(screen.queryByRole("combobox", { name: "직위" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("combobox", { name: "팀" }));
    const listbox = await screen.findByRole("listbox");
    expect(
      within(listbox)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["인사팀", "선택 안 함 (부서 직속)"]);
  });

  it("승인 대기에서 새로고침했는데 승인됐으면 운영진 홈으로 간다", async () => {
    mockStaff(registration());
    const user = userEvent.setup();
    const { router } = await renderRoute("/staff/registration");
    expect(await screen.findByText("교육운영본부")).toBeInTheDocument();
    expect(screen.getByText("교육 1팀")).toBeInTheDocument();
    expect(screen.getByText("백엔드 부트캠프")).toBeInTheDocument();
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
        reject_reason: "담당 과정을 다시 확인해 주세요.",
        reviewed_at: "2026-11-16T06:02:00Z",
      }),
    );
    const user = userEvent.setup();
    await renderRoute("/staff/registration");
    expect(await screen.findByRole("alert")).toHaveTextContent("담당 과정을 다시 확인해 주세요.");
    await user.click(screen.getByRole("button", { name: "고쳐서 다시 신청" }));
    expect(await screen.findByRole("combobox", { name: "팀" })).toHaveTextContent("교육 1팀");
    expect(
      within(screen.getByRole("list", { name: "추가한 담당 과정" })).getByText("백엔드 부트캠프"),
    ).toBeInTheDocument();
  });
});
