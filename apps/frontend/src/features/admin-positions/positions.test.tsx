import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import type { OrgImpact } from "@/features/admin-org/api";
import { iGa } from "@/features/admin-org/text";
import type { PermissionDef, Position } from "@/features/admin-permissions/api";
import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { move, nextPriority, orderChanged, priorityChanges } from "./order";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: false });

function position(id: string, name: string, priority: number, extra: Partial<Position> = {}): Position {
  return {
    id,
    name,
    priority,
    assignment_scope: "COURSE",
    data_scope: "ASSIGNED",
    permissions: [],
    employee_count: 0,
    ...extra,
  };
}

const LEAD = position("p1", "팀리드", 10, { assignment_scope: null, data_scope: "ALL", employee_count: 2 });
const MANAGER = position("p2", "운영 매니저", 20, {
  permissions: ["academy.cohort.read", "mentoring.chat.read"],
  employee_count: 1,
});
const ASSISTANT = position("p3", "조교", 30, { assignment_scope: "COHORT" });
const DEFS: PermissionDef[] = [
  {
    code: "academy.cohort.read",
    area: "학사",
    entity: "기수",
    action: "조회",
    description: "",
    cohort_bound: true,
    requires: null,
  },
  {
    code: "mentoring.chat.read",
    area: "멘토링",
    entity: "채팅",
    action: "조회",
    description: "",
    cohort_bound: true,
    requires: null,
  },
];
const IMPACT: OrgImpact = {
  employees: [
    {
      id: "e1",
      user_id: "u1",
      name: "김운영",
      email: "manager@nextrunners.co.kr",
      department_name: "교육운영본부",
      team_name: "교육 1팀",
      position_name: "운영 매니저",
    },
  ],
  registrations: [],
  teams: [],
  bootcamps: [],
};

function access(codes: string[]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: [],
  };
}

const MANAGE = ["org.position.read", "org.position.manage", "access.role.read"];

function mockApi({ codes = MANAGE } = {}) {
  const calls: { method: string; id?: string; body?: unknown }[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes))),
    http.get(apiUrl("/api/v1/admin/positions"), () => HttpResponse.json([ASSISTANT, LEAD, MANAGER])),
    http.get(apiUrl("/api/v1/admin/permissions"), () => HttpResponse.json(DEFS)),
    http.get(apiUrl("/api/v1/admin/positions/{position_id}/impact"), ({ params }) =>
      HttpResponse.json(params.position_id === "p2" ? IMPACT : { ...IMPACT, employees: [] }),
    ),
    http.patch(apiUrl("/api/v1/admin/positions/{position_id}"), async ({ request, params }) => {
      const body = (await request.json()) as Partial<Position>;
      calls.push({ method: "PATCH", id: String(params.position_id), body });
      return HttpResponse.json({ ...MANAGER, ...body });
    }),
    http.post(apiUrl("/api/v1/admin/positions"), async ({ request }) => {
      const body = (await request.json()) as Partial<Position>;
      calls.push({ method: "POST", body });
      if (body.name === "조교")
        return HttpResponse.json(
          { error: { code: "position_name_taken", message: "같은 이름의 직위가 있습니다." } },
          { status: 409 },
        );
      return HttpResponse.json({ ...MANAGER, id: "p9", ...body }, { status: 201 });
    }),
    http.delete(apiUrl("/api/v1/admin/positions/{position_id}"), ({ params }) => {
      calls.push({ method: "DELETE", id: String(params.position_id) });
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return calls;
}

describe("직위 순서 (F70)", () => {
  it("옮기기·바뀜 판단·저장할 priority·새 직위 자리", () => {
    const list = [LEAD, MANAGER, ASSISTANT];
    const moved = move(list, 2, 0);
    expect(moved.map((p) => p.id)).toEqual(["p3", "p1", "p2"]);
    expect(orderChanged(list, moved)).toBe(true);
    expect(orderChanged(list, [...list])).toBe(false);
    expect(priorityChanges(moved)).toEqual([
      { id: "p3", priority: 10 },
      { id: "p1", priority: 20 },
      { id: "p2", priority: 30 },
    ]);
    expect(priorityChanges(list)).toEqual([]);
    expect(nextPriority(list)).toBe(40);
    expect(iGa("조교")).toBe("조교가");
    expect(iGa("팀리드")).toBe("팀리드가");
    expect(iGa("운영 매니저")).toBe("운영 매니저가");
    expect(iGa("인사 담당")).toBe("인사 담당이");
  });
});

describe("조직 설정 > 직위 (FE-15h)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("우선순위순 표, 키보드로 순서를 바꿔 저장한다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/org/positions");
    const table = await screen.findByRole("table", { name: "직위" });
    const names = () =>
      within(table)
        .getAllByRole("row")
        .slice(1)
        .map((r) => r.getAttribute("aria-label"));
    expect(names()).toEqual(["팀리드", "운영 매니저", "조교"]);
    expect(within(table).getByRole("row", { name: "조교" })).toHaveTextContent("기수 담당");
    const menu = screen.getByRole("navigation", { name: "메뉴" });
    expect(within(menu).getByRole("link", { name: "직위" })).toHaveAttribute("aria-current", "page");

    const user = userEvent.setup();
    within(table)
      .getByRole("button", { name: /조교 순서 옮기기/ })
      .focus();
    await user.keyboard("{ArrowUp}");
    expect(names()).toEqual(["팀리드", "조교", "운영 매니저"]);
    expect(screen.getByText("순서가 바뀌었어요")).toBeInTheDocument();
    expect(screen.getByText(/조교가 2번째로/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "되돌리기" }));
    expect(names()).toEqual(["팀리드", "운영 매니저", "조교"]);

    within(table)
      .getByRole("button", { name: /조교 순서 옮기기/ })
      .focus();
    await user.keyboard("{ArrowUp}");
    await user.click(screen.getByRole("button", { name: "순서 저장" }));
    await waitFor(() =>
      expect(calls).toEqual([
        { method: "PATCH", id: "p3", body: { priority: 20 } },
        { method: "PATCH", id: "p2", body: { priority: 30 } },
      ]),
    );
  });

  it("패널: 기본 정보·직원·권한(영역별 접힘), 머리에 [수정][삭제]", async () => {
    mockApi();
    await renderRoute("/admin/org/positions?position=p2");
    const sheet = await screen.findByRole("dialog", { name: "운영 매니저" });
    expect(within(sheet).getByText("직위 · 2번째")).toBeInTheDocument();
    expect(within(sheet).getByRole("region", { name: "기본 정보" })).toHaveTextContent("과정 담당");
    expect(await within(sheet).findByRole("list", { name: "직원" })).toHaveTextContent("김운영");
    const area = await within(sheet).findByRole("button", { name: /학사/ });
    expect(area).toHaveAttribute("aria-expanded", "false");
    const user = userEvent.setup();
    await user.click(area);
    expect(within(sheet).getByRole("list", { name: "학사" })).toHaveTextContent("기수 · 조회");
    expect(within(sheet).getByRole("button", { name: "수정" })).toBeInTheDocument();
    expect(within(sheet).getByRole("button", { name: "삭제" })).toBeInTheDocument();
  });

  it("담당 방식을 바꾸면 바뀐 항목과 영향받는 대상을 확인하고 저장한다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/org/positions?position=p2");
    const sheet = await screen.findByRole("dialog", { name: "운영 매니저" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "수정" }));
    await user.click(within(sheet).getByRole("combobox", { name: "담당 방식" }));
    await user.click(await screen.findByRole("option", { name: "기수 담당" }));
    await user.click(within(sheet).getByRole("button", { name: "저장" }));
    const dialog = await screen.findByRole("dialog", { name: "운영 매니저 직위를 바꿀까요?" });
    expect(within(dialog).getByRole("region", { name: "바뀐 항목" })).toHaveTextContent("과정 담당 → 기수 담당");
    await user.click(await within(dialog).findByRole("button", { name: /직원\s*1명/ }));
    expect(within(dialog).getByRole("list", { name: "직원" })).toHaveTextContent("김운영");
    await user.click(within(dialog).getByRole("button", { name: "저장" }));
    await waitFor(() =>
      expect(calls).toEqual([
        {
          method: "PATCH",
          id: "p2",
          body: { name: "운영 매니저", assignment_scope: "COHORT", data_scope: "ASSIGNED" },
        },
      ]),
    );
  });

  it("직원이 있는 직위는 지울 수 없어 목록과 [닫기]만 보인다", async () => {
    mockApi();
    await renderRoute("/admin/org/positions?position=p2");
    const user = userEvent.setup();
    await user.click(
      within(await screen.findByRole("dialog", { name: "운영 매니저" })).getByRole("button", { name: "삭제" }),
    );
    const blocked = await screen.findByRole("dialog", { name: "운영 매니저를 지울 수 없어요" });
    expect(within(blocked).getByText("닫기", { selector: "button" })).toBeInTheDocument();
    expect(within(blocked).queryByText("삭제", { selector: "button" })).not.toBeInTheDocument();
  });

  it("직위 추가: 맨 아래 순서로 만들고, 같은 이름이면 이름 칸에 알린다", async () => {
    const calls = mockApi();
    await renderRoute("/admin/org/positions");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "직위 추가" }));
    const sheet = await screen.findByRole("dialog", { name: "새 직위" });
    await user.type(within(sheet).getByRole("textbox", { name: "이름" }), "조교");
    await user.click(within(sheet).getByRole("button", { name: "저장" }));
    expect(await within(sheet).findByText("같은 이름의 직위가 있어요.")).toBeInTheDocument();
    expect(calls[0]).toEqual({
      method: "POST",
      body: { name: "조교", priority: 40, assignment_scope: null, data_scope: "ASSIGNED" },
    });
  });

  it("조회 권한만 있으면 손잡이·추가·수정·삭제가 없고 직원은 수만", async () => {
    mockApi({ codes: ["org.position.read"] });
    await renderRoute("/admin/org/positions?position=p2");
    const sheet = await screen.findByRole("dialog", { name: "운영 매니저" });
    expect(within(sheet).queryByRole("button", { name: "수정" })).not.toBeInTheDocument();
    expect(within(sheet).queryByRole("region", { name: "직원" })).not.toBeInTheDocument();
    expect(within(sheet).getByText("권한 내용은 권한 메뉴에서 볼 수 있어요.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /순서 옮기기/, hidden: true })).not.toBeInTheDocument();
  });
});
