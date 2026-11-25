import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { RosterStudent, StudentDetail } from "./api";
import { groupStudents, matches } from "./filter";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: false });

const student = (id: string, name: string, extra: Partial<RosterStudent> = {}): RosterStudent => ({
  id,
  airtable_record_id: `rec${id}`,
  name,
  phone_number: "01012341234",
  email: `${id}@example.com`,
  status: "ENROLLED",
  hrd_net_status: "TRAINING",
  user_id: null,
  is_removed_in_source: false,
  enrolled_at: "2026-06-02",
  ended_at: null,
  end_reason: null,
  synced_at: "2026-11-24T18:00:00Z",
  ...extra,
});
const GA = student("s1", "가수강", { user_id: "u1" });
const NA = student("s2", "나하늘", { phone_number: "01055556666" });
const DA = student("s3", "다도윤", { status: "DROPPED", ended_at: "2026-09-01", end_reason: "개인 사정" });

const COHORTS = [
  {
    id: "c12",
    bootcamp_id: "b1",
    bootcamp_name: "백엔드 부트캠프",
    cohort_number: 12,
    start_date: "2026-06-02",
    end_date: "2026-11-30",
    status: "ONGOING",
  },
  {
    id: "c11",
    bootcamp_id: "b1",
    bootcamp_name: "백엔드 부트캠프",
    cohort_number: 11,
    start_date: "2025-12-01",
    end_date: "2026-05-29",
    status: "ENDED",
  },
  {
    id: "f3",
    bootcamp_id: "b2",
    bootcamp_name: "프론트엔드 부트캠프",
    cohort_number: 3,
    start_date: "2026-06-02",
    end_date: "2026-11-30",
    status: "ONGOING",
  },
] as StaffAccess["cohorts"];

const DETAIL: StudentDetail = {
  ...GA,
  member: { user_id: "u1", email: "ga@gmail.com", approved_at: "2026-11-03T01:00:00Z" },
  mentoring: {
    team_id: null,
    team_label: null,
    account: {
      id: "a1",
      valid_from: "2026-06-02",
      valid_until: "2026-11-30",
      is_expired: false,
      total_minutes: 360,
      held_minutes: 60,
      used_minutes: 180,
      remaining_minutes: 120,
    },
    pending_request_count: 1,
    upcoming_session_count: 0,
    completed_session_count: 3,
  },
};

function access(codes: string[]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: COHORTS,
  };
}

function mockApi({ codes = ["academy.roster.read", "mentoring.request.read"] } = {}) {
  const rosters: string[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes))),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/rosters"), ({ params }) => {
      rosters.push(String(params.cohort_id));
      return HttpResponse.json(params.cohort_id === "c12" ? [GA, NA, DA] : []);
    }),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/students/{student_id}"), () => HttpResponse.json(DETAIL)),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentoring/requests"), () =>
      HttpResponse.json({
        items: [
          {
            id: "r1",
            status: "PENDING",
            topic: "포트폴리오 리뷰",
            duration: 60,
            desired_times: ["2026-11-27T05:00:00Z"],
            mentor_display_name: "멘토K",
            session: null,
            created_at: "2026-11-24T01:00:00Z",
          },
        ],
        total: 1,
        limit: 3,
        offset: 0,
      }),
    ),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/mentoring/sessions"), () =>
      HttpResponse.json({
        items: [
          {
            id: "x1",
            status: "COMPLETED",
            topic: "README 구성",
            starts_at: "2026-11-16T01:00:00Z",
            ends_at: "2026-11-16T02:00:00Z",
            mentor_display_name: "멘토K",
            team_label: null,
            record_duration_minutes: 60,
          },
        ],
        total: 1,
        limit: 3,
        offset: 0,
      }),
    ),
  );
  return { rosters };
}

describe("검색어 일치", () => {
  it("이름·이메일은 부분 일치, 휴대폰은 숫자 3자리 이상", () => {
    expect(matches(NA, "하늘")).toBe(true);
    expect(matches(NA, "S2@EXAMPLE")).toBe(true);
    expect(matches(NA, "5555")).toBe(true);
    expect(matches(NA, "55")).toBe(false);
    expect(matches(NA, "")).toBe(true);
  });
});

describe("묶어 보기", () => {
  it("수강 상태는 탭 순서, 가입 상태는 가입 → 미가입, 빈 묶음은 뺀다", () => {
    expect(groupStudents([GA, NA, DA], "status").map((g) => [g.label, g.items.length])).toEqual([
      ["수강 중", 2],
      ["중도 포기", 1],
    ]);
    expect(groupStudents([GA, NA, DA], "signup").map((g) => [g.label, g.items.map((s) => s.name)])).toEqual([
      ["가입", ["가수강"]],
      ["미가입", ["나하늘", "다도윤"]],
    ]);
  });
});

describe("학사 > 수강생 (FE-17c)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("기수를 고르지 않으면 담당 기수 중 첫 기수, 상태 탭 건수와 표", async () => {
    const { rosters } = mockApi();
    await renderRoute("/admin/academy/students");
    const table = await screen.findByRole("table", { name: "수강생" });
    expect(rosters).toEqual(["c12"]);
    expect(within(table).getByRole("row", { name: "가수강" })).toHaveTextContent(
      "010-****-1234s1@example.com가입수강 중",
    );
    expect(within(table).getByRole("row", { name: "나하늘" })).toHaveTextContent("미가입");
    const tabs = screen.getByRole("navigation", { name: "수강 상태" });
    expect(within(tabs).getByRole("link", { name: "전체 3" })).toHaveAttribute("aria-current", "page");
    expect(within(tabs).getByRole("link", { name: "중도 포기 1" })).toBeInTheDocument();
    const menu = screen.getByRole("navigation", { name: "메뉴" });
    expect(within(menu).getByRole("link", { name: "수강생" })).toHaveAttribute("aria-current", "page");
  });

  it("상태 탭과 검색으로 거른다", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/academy/students?cohort=c12");
    await screen.findByRole("table", { name: "수강생" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("link", { name: "중도 포기 1" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ cohort: "c12", status: "DROPPED" }));
    expect(within(screen.getByRole("table", { name: "수강생" })).getAllByRole("row")).toHaveLength(2);
  });

  it("검색은 이름·휴대폰·이메일로 거른다", async () => {
    mockApi();
    await renderRoute("/admin/academy/students?cohort=c12");
    await screen.findByRole("table", { name: "수강생" });
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox", { name: "수강생 검색" }), "5555");
    await waitFor(() =>
      expect(
        within(screen.getByRole("table", { name: "수강생" }))
          .getAllByRole("row")
          .slice(1)
          .map((r) => r.getAttribute("aria-label")),
      ).toEqual(["나하늘"]),
    );
  });

  it("과정을 바꾸면 그 과정의 첫 기수", async () => {
    const { rosters } = mockApi();
    const { router } = await renderRoute("/admin/academy/students?cohort=c12");
    await screen.findByRole("table", { name: "수강생" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("combobox", { name: "과정" }));
    await user.click(await screen.findByRole("option", { name: "프론트엔드 부트캠프" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ cohort: "f3" }));
    expect(await screen.findByText("수강생이 없어요")).toBeInTheDocument();
    expect(rosters.at(-1)).toBe("f3");
  });

  it("상세 기본 정보 탭", async () => {
    mockApi();
    await renderRoute("/admin/academy/students/s1?cohort=c12");
    expect(await screen.findByRole("heading", { name: "가수강" })).toBeInTheDocument();
    const basic = screen.getByRole("region", { name: "기본·수강 정보" });
    expect(basic).toHaveTextContent("휴대폰010-****-1234");
    expect(basic).toHaveTextContent("기수백엔드 부트캠프 12기");
    expect(basic).toHaveTextContent("HRD 상태수강 중");
    expect(basic).toHaveTextContent("가입 계정2026.11.03 승인 · ga@gmail.com");
    expect(basic).toHaveTextContent("명단 원천Airtable · 11/25 03:00 동기화");
  });

  it("상세 멘토링 탭: 요약 카드와 최근 신청·세션", async () => {
    mockApi();
    await renderRoute("/admin/academy/students/s1?cohort=c12&tab=mentoring");
    const summary = await screen.findByRole("region", { name: "멘토링 요약" });
    expect(summary).toHaveTextContent("잔여2시간");
    expect(summary).toHaveTextContent("보류1시간대기 중인 신청 1건");
    expect(summary).toHaveTextContent("사용3시간완료 세션 3회");
    expect(summary).toHaveTextContent("팀없음1:1 멘토링만");
    const recent = await screen.findByRole("table", { name: "최근 신청·세션" });
    const rows = within(recent).getAllByRole("row").slice(1);
    expect(rows.map((r) => r.textContent)).toEqual([
      expect.stringContaining("포트폴리오 리뷰60분멘토K신청대기"),
      expect.stringContaining("README 구성기록 60분멘토K세션완료"),
    ]);
  });

  it("신청 조회 권한이 없으면 최근 신청·세션을 숨긴다", async () => {
    mockApi({ codes: ["academy.roster.read"] });
    await renderRoute("/admin/academy/students/s1?cohort=c12&tab=mentoring");
    await screen.findByRole("region", { name: "멘토링 요약" });
    expect(screen.queryByRole("region", { name: "최근 신청·세션" })).not.toBeInTheDocument();
  });

  it("가입 상태별로 묶고 묶음을 접는다, 상태 탭과 함께 쓴다 (F77)", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/academy/students?cohort=c12");
    await screen.findByRole("table", { name: "수강생" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("combobox", { name: "묶어 보기" }));
    await user.click(await screen.findByRole("option", { name: "가입 상태별" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ cohort: "c12", group: "signup" }));
    const table = screen.getByRole("table", { name: "수강생" });
    const unsigned = within(table).getByRole("rowgroup", { name: "미가입 2명" });
    expect(
      within(unsigned)
        .getAllByRole("row")
        .slice(1)
        .map((r) => r.getAttribute("aria-label")),
    ).toEqual(["나하늘", "다도윤"]);
    await user.click(within(unsigned).getByRole("button", { name: /미가입/ }));
    expect(within(unsigned).getAllByRole("row")).toHaveLength(1);

    await user.click(screen.getByRole("link", { name: "중도 포기 1" }));
    await waitFor(() =>
      expect(router.state.location.search).toEqual({ cohort: "c12", status: "DROPPED", group: "signup" }),
    );
    expect(within(screen.getByRole("table", { name: "수강생" })).getAllByRole("rowgroup")).toHaveLength(1);
  });
});
