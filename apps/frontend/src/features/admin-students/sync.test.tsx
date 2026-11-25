import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { SyncRun } from "./sync-api";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: false });

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
] as StaffAccess["cohorts"];

const run = (id: string, extra: Partial<SyncRun> = {}): SyncRun => ({
  id,
  trigger: "SCHEDULED",
  scope_type: "ALL",
  bootcamp_id: null,
  cohort_id: null,
  status: "SUCCEEDED",
  started_at: "2026-11-25T04:59:00Z",
  finished_at: "2026-11-25T05:00:00Z",
  fetched_count: 4383,
  upserted_count: 12,
  removed_count: 1,
  unmapped_count: 2,
  error_message: null,
  ...extra,
});

function access(global: boolean, codes = ["academy.roster.read", "academy.roster.sync"]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: global, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: COHORTS,
  };
}

function mockApi({ global = true, codes }: { global?: boolean; codes?: string[] } = {}) {
  const started: string[] = [];
  let polls = 0;
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(global, codes))),
    http.get(apiUrl("/api/v1/admin/cohorts/{cohort_id}/rosters"), () => HttpResponse.json([])),
    http.get(apiUrl("/api/v1/admin/rosters/sync-runs"), () =>
      HttpResponse.json({
        items: [
          run("r2"),
          run("r1", {
            status: "FAILED",
            trigger: "MANUAL",
            scope_type: "COHORT",
            cohort_id: "c12",
            error_message: "Airtable 응답이 없어요",
          }),
        ],
        next_before: null,
      }),
    ),
    http.get(apiUrl("/api/v1/admin/rosters/unmapped"), () =>
      HttpResponse.json({
        run_id: "r2",
        finished_at: "2026-11-25T05:00:00Z",
        records: [
          { airtable_record_id: "recA", name: "김하나", cohort_label: "헬스케어 3기", reason: "cohort_not_found" },
        ],
      }),
    ),
    http.post(apiUrl("/api/v1/admin/cohorts/{cohort_id}/rosters/sync"), ({ params }) => {
      started.push(`cohort:${String(params.cohort_id)}`);
      return HttpResponse.json(
        run("new", { status: "RUNNING", trigger: "MANUAL", scope_type: "COHORT", finished_at: null }),
        { status: 202 },
      );
    }),
    http.post(apiUrl("/api/v1/admin/bootcamps/{bootcamp_id}/rosters/sync"), ({ params }) => {
      started.push(`bootcamp:${String(params.bootcamp_id)}`);
      return HttpResponse.json(run("new", { status: "RUNNING", finished_at: null }), { status: 202 });
    }),
    http.get(apiUrl("/api/v1/admin/rosters/sync-runs/{run_id}"), () => {
      polls += 1;
      return HttpResponse.json(run("new", { upserted_count: 3 }));
    }),
  );
  return { started, polls: () => polls };
}

describe("학사 > 수강생 > 명단 동기화 (FE-17d)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("머리에 마지막 동기화, 패널에 실행 이력과 매핑 실패", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/academy/students?cohort=c12");
    expect(await screen.findByText("마지막 동기화 11/25 14:00 · 매시간 자동")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "명단 동기화" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ cohort: "c12", sync: true }));
    const sheet = await screen.findByRole("dialog", { name: "명단 동기화" });
    const runs = await within(sheet).findByRole("list", { name: "실행 이력" });
    expect(
      within(runs)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual([
      expect.stringContaining("성공전체 · 자동11/25 14:00가져옴 4,383 · 반영 12 · 빠짐 1 · 매핑 실패 2"),
      expect.stringContaining("실패기수 · 백엔드 부트캠프 12기 · 수동11/25 14:00Airtable 응답이 없어요"),
    ]);
    expect(await within(sheet).findByRole("list", { name: "매핑 실패" })).toHaveTextContent(
      "김하나헬스케어 3기기수를 찾지 못함",
    );
  });

  it("대상 유형을 고르면 필요한 선택지만 차례로 나타나고, 실행하면 결과를 알린다", async () => {
    const { started, polls } = mockApi();
    await renderRoute("/admin/academy/students?cohort=c12&sync=1");
    const sheet = await screen.findByRole("dialog", { name: "명단 동기화" });
    const runButton = within(sheet).getByRole("button", { name: "동기화 실행" });
    expect(runButton).toBeDisabled();
    expect(within(sheet).queryByRole("combobox", { name: "과정" })).not.toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("combobox", { name: "대상 유형" }));
    await user.click(await screen.findByRole("option", { name: "기수" }));
    expect(within(sheet).queryByRole("combobox", { name: "기수" })).not.toBeInTheDocument();
    await user.click(within(sheet).getByRole("combobox", { name: "과정" }));
    await user.click(await screen.findByRole("option", { name: "백엔드 부트캠프" }));
    await user.click(within(sheet).getByRole("combobox", { name: "기수" }));
    await user.click(await screen.findByRole("option", { name: "11기" }));
    expect(runButton).toBeEnabled();
    await user.click(runButton);
    await waitFor(() => expect(started).toEqual(["cohort:c11"]));
    expect(
      await screen.findByText(/명단을 동기화했어요 \(가져옴 4,383 · 반영 3/, {}, { timeout: 6000 }),
    ).toBeInTheDocument();
    expect(polls()).toBe(1);
  }, 10000);

  it("과정 유형이면 과정만 고른다", async () => {
    const { started } = mockApi();
    await renderRoute("/admin/academy/students?cohort=c12&sync=1");
    const sheet = await screen.findByRole("dialog", { name: "명단 동기화" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("combobox", { name: "대상 유형" }));
    await user.click(await screen.findByRole("option", { name: "과정" }));
    await user.click(within(sheet).getByRole("combobox", { name: "과정" }));
    await user.click(await screen.findByRole("option", { name: "백엔드 부트캠프" }));
    expect(within(sheet).queryByRole("combobox", { name: "기수" })).not.toBeInTheDocument();
    await user.click(within(sheet).getByRole("button", { name: "동기화 실행" }));
    await waitFor(() => expect(started).toEqual(["bootcamp:b1"]));
  });

  it("담당 범위 권한이면 '전체'와 매핑 실패가 없다", async () => {
    mockApi({ global: false });
    await renderRoute("/admin/academy/students?cohort=c12&sync=1");
    const sheet = await screen.findByRole("dialog", { name: "명단 동기화" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("combobox", { name: "대상 유형" }));
    expect(screen.queryByRole("option", { name: "전체" })).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(within(sheet).queryByRole("region", { name: /매핑 실패/ })).not.toBeInTheDocument();
  });

  it("동기화 권한이 없으면 실행 섹션이 없다", async () => {
    mockApi({ codes: ["academy.roster.read"] });
    await renderRoute("/admin/academy/students?cohort=c12&sync=1");
    const sheet = await screen.findByRole("dialog", { name: "명단 동기화" });
    await within(sheet).findByRole("list", { name: "실행 이력" });
    expect(within(sheet).queryByRole("button", { name: "동기화 실행" })).not.toBeInTheDocument();
  });
});
