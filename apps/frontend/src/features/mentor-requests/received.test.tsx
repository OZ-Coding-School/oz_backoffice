import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { MentoringRequest, RequestCounts } from "@/features/requests/api";
import { makeRequest } from "@/features/requests/test-utils";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { desiredLabel } from "./labels";

const MENTOR = makeMe({
  id: "u9",
  name: "김멘토",
  account_type: "MENTOR",
  roles: [{ role: "MENTOR", scope_type: "GLOBAL", scope_id: null, expires_at: null }],
});

const PENDING = makeRequest({
  desired_times: ["2026-11-24T10:00:00Z", "2026-11-25T10:00:00Z", "2026-11-26T11:00:00Z"],
});
const TEAM = makeRequest({
  id: "r2",
  topic: "팀 배포 구성 점검",
  team_id: "t3",
  team_label: "3팀 알파",
  desired_times: ["2026-11-25T11:00:00Z"],
  created_at: "2026-11-16T00:20:00Z",
});
const APPROVED = makeRequest({
  id: "r3",
  status: "APPROVED",
  topic: "포트폴리오 리뷰",
  session: { id: "s1", starts_at: "2026-11-20T05:00:00Z", ends_at: "2026-11-20T06:00:00Z" },
  bootcamp_name: "프론트엔드",
  cohort_number: 9,
  cohort_id: "c9",
});
const REJECTED = makeRequest({ id: "r4", status: "REJECTED", topic: "알고리즘 질문" });
const ALL = [PENDING, TEAM, APPROVED, REJECTED];

const ASSIGNMENTS = [
  { cohort_id: "c12", bootcamp_name: "초격차 백엔드", cohort_number: 12, start_date: "2026-10-01" },
  { cohort_id: "c9", bootcamp_name: "프론트엔드", cohort_number: 9, start_date: "2026-03-01" },
].map((a, i) => ({
  ...a,
  id: `a${i}`,
  end_date: "2027-03-31",
  is_active: i === 0,
  deactivated_at: null,
  deactivation_reason: null,
  cost_settlement_policy: "PAID" as const,
  pay_unit: "HOURLY" as const,
  pay_rate: 50000,
  no_show_pay_amount: null,
}));

/** status·cohort_id로 거르고 counts는 기수만 따른다 (A76) */
function mockReceived(items: MentoringRequest[]) {
  const seen: URLSearchParams[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/mentor-requests"), ({ request }) => {
      const params = new URL(request.url).searchParams;
      seen.push(params);
      const status = params.getAll("status");
      const cohort = params.get("cohort_id");
      const inCohort = items.filter((r) => !cohort || r.cohort_id === cohort);
      const found = inCohort.filter((r) => status.length === 0 || status.includes(r.status));
      const counts: RequestCounts = { PENDING: 0, APPROVED: 0, REJECTED: 0, CANCELED: 0 };
      for (const r of inCohort) counts[r.status] += 1;
      return HttpResponse.json({ items: found, total: found.length, limit: 20, offset: 0, counts });
    }),
    http.get(apiUrl("/api/v1/me/mentor-assignments"), () => HttpResponse.json(ASSIGNMENTS)),
  );
  return seen;
}

beforeEach(() => {
  resetAuth();
  mockSignedIn(MENTOR);
});

describe("희망 일시 칸 (F43)", () => {
  it("대기는 이른 희망 일시와 '외 N', 승인은 확정 일시, 반려·취소는 '—'", () => {
    expect(desiredLabel(PENDING)).toBe("11/24(화) 19:00 외 2");
    expect(desiredLabel(TEAM)).toBe("11/25(수) 20:00");
    expect(desiredLabel(APPROVED)).toBe("11/20(금) 14:00");
    expect(desiredLabel(REJECTED)).toBe("—");
  });
});

describe("멘토 받은 신청 목록 (F43)", () => {
  it("기본은 대기 탭이고, 탭마다 건수를 보여 주며 행에 신청자·기수·희망 일시를 보여 준다", async () => {
    const seen = mockReceived(ALL);
    await renderRoute("/mentor/requests");
    expect(await screen.findByRole("heading", { name: "받은 신청", level: 1 })).toBeInTheDocument();
    const tabs = screen.getByRole("navigation", { name: "신청 상태" });
    expect(await within(tabs).findByRole("link", { name: "대기 2" })).toHaveAttribute("aria-current", "page");
    expect(within(tabs).getByRole("link", { name: "승인 1" })).toHaveAttribute("href", "/mentor/requests?tab=approved");
    expect(within(tabs).getByRole("link", { name: "전체 4" })).toBeInTheDocument();
    expect(seen[0]?.getAll("status")).toEqual(["PENDING"]);

    const table = screen.getByRole("table");
    const row = within(table).getByRole("row", { name: /Django ORM 질문/ });
    expect(row).toHaveTextContent("11/16 10:02");
    expect(row).toHaveTextContent("60분 · 초격차 백엔드 12기");
    expect(row).toHaveTextContent("가수강 · 1:1");
    expect(row).toHaveTextContent("11/24(화) 19:00 외 2");
    expect(within(row).getByText("대기")).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: /팀 배포 구성 점검/ })).toHaveTextContent("3팀 알파 · 팀");
    // 휴대폰·태블릿 카드
    expect(screen.getByRole("article", { name: "Django ORM 질문" })).toHaveTextContent("희망 11/24(화) 19:00 외 2");
  });

  it("기수를 고르면 그 기수로 거르고 탭 건수도 따른다 (A76)", async () => {
    const seen = mockReceived(ALL);
    const { router } = await renderRoute("/mentor/requests?tab=all");
    expect(await screen.findByRole("link", { name: "전체 4" })).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("combobox", { name: "기수" }));
    const options = await screen.findAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual(["전체 기수", "초격차 백엔드 12기", "프론트엔드 9기"]);
    await userEvent.setup().click(screen.getByRole("option", { name: "프론트엔드 9기" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "all", cohort: "c9" }));
    expect(await screen.findByRole("link", { name: "전체 1" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "대기 0" })).toHaveAttribute("href", "/mentor/requests?cohort=c9");
    expect(seen.at(-1)?.get("cohort_id")).toBe("c9");
  });

  it("신청이 없으면 빈 상태를 보여 준다", async () => {
    mockReceived([]);
    await renderRoute("/mentor/requests");
    expect(await screen.findByRole("heading", { name: "아직 받은 신청이 없어요" })).toBeInTheDocument();
  });

  it("메뉴에 받은 신청과 대기 건수 배지가 있다 (F44)", async () => {
    mockReceived(ALL);
    await renderRoute("/");
    await screen.findByRole("heading", { name: "안녕하세요, 김멘토님" });
    const menu = screen.getAllByRole("navigation", { name: "메뉴" })[0]!;
    expect(await within(menu).findByRole("link", { name: /^받은 신청\s*대기\s*2$/ })).toHaveAttribute(
      "href",
      "/mentor/requests",
    );
  });

  it("수강생은 받은 신청에 들어오면 홈으로 간다", async () => {
    mockSignedIn(makeMe());
    const { router } = await renderRoute("/mentor/requests");
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });
});
