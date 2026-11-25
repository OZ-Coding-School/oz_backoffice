import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { StaffAccess } from "@/features/staff/api";
import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import type { HrdBootcamp, HrdCohort } from "./api";

const ADMIN = makeMe({ name: "김관리", account_type: "STAFF", is_super_admin: false });

const BE: HrdBootcamp = {
  id: "h1",
  name: "백엔드 KDT",
  hrd_net_id: "AIG1",
  train_type: "KDT",
  ncs1_se: "20",
  ncs2_se: "01",
  ncs3_se: "02",
  weekend_se: "WEEKDAY",
  day_night_se: "DAY",
  total_train_fee: 11200000,
  train_fee_per_hour: 12000,
  total_train_hours: 960,
  total_train_days: 120,
  bootcamps: [
    { id: "b1", name: "백엔드 부트캠프", code: "BE" },
    { id: "b7", name: "CEO 과정", code: "CEO" },
  ],
  cohort_count: 2,
};
const DA: HrdBootcamp = {
  ...BE,
  id: "h2",
  name: "데이터 분석 KDC",
  hrd_net_id: null,
  train_type: "KDC",
  bootcamps: [],
  cohort_count: 0,
};
const R15: HrdCohort = {
  id: "r15",
  hrd_net_bootcamp_id: "h1",
  cohort_number: 15,
  train_start_date: "2026-06-02",
  train_end_date: "2026-11-30",
  self_pay_amount: 1120000,
  linked_cohorts: [
    { id: "c12", bootcamp_id: "b1", bootcamp_name: "백엔드 부트캠프", cohort_number: 12 },
    { id: "c1", bootcamp_id: "b7", bootcamp_name: "CEO 과정", cohort_number: 1 },
  ],
};
const R16: HrdCohort = { ...R15, id: "r16", cohort_number: 16, self_pay_amount: null, linked_cohorts: [] };

function access(codes: string[]): StaffAccess {
  return {
    is_super_admin: false,
    position: null,
    permissions: codes.map((code) => ({ code, is_global: true, bootcamp_ids: [], cohort_ids: [] })),
    cohorts: [],
  };
}

function mockApi({ codes = ["academy.hrd.read", "academy.hrd.manage"] } = {}) {
  const patches: { path: string; body: unknown }[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/staff-access"), () => HttpResponse.json(access(codes))),
    http.get(apiUrl("/api/v1/admin/hrd-bootcamps"), () => HttpResponse.json([BE, DA])),
    http.get(apiUrl("/api/v1/admin/hrd-bootcamps/{hrd_bootcamp_id}/cohorts"), ({ params }) =>
      HttpResponse.json(params.hrd_bootcamp_id === "h1" ? [R15, R16] : []),
    ),
    http.patch(apiUrl("/api/v1/admin/hrd-bootcamps/{hrd_bootcamp_id}"), async ({ request }) => {
      const body = (await request.json()) as Partial<HrdBootcamp>;
      patches.push({ path: "hrd", body });
      return HttpResponse.json({ ...BE, ...body });
    }),
    http.patch(apiUrl("/api/v1/admin/hrd-cohorts/{hrd_cohort_id}"), async ({ request }) => {
      const body = (await request.json()) as Partial<HrdCohort>;
      patches.push({ path: "cohort", body });
      return HttpResponse.json({ ...R15, ...body });
    }),
  );
  return { patches };
}

describe("학사 > HRD 과정 (FE-17b)", () => {
  beforeEach(() => {
    resetAuth();
    mockSignedIn(ADMIN);
  });

  it("HRD 과정 표: 이름·훈련과정 ID·유형·회차 수·연결 운영과정", async () => {
    mockApi();
    await renderRoute("/admin/academy/hrd");
    const table = await screen.findByRole("table", { name: "HRD 과정" });
    expect(within(table).getByRole("row", { name: "백엔드 KDT" })).toHaveTextContent(
      "백엔드 KDTAIG1KDT2백엔드 부트캠프 · CEO 과정",
    );
    expect(within(table).getByRole("row", { name: "데이터 분석 KDC" })).toHaveTextContent("—KDC0—");
    const menu = screen.getByRole("navigation", { name: "메뉴" });
    expect(within(menu).getByRole("link", { name: "HRD 과정" })).toHaveAttribute("aria-current", "page");
  });

  it("HRD 과정 패널: 훈련 정보·연결 운영과정·회차(최근부터), 회차를 누르면 회차 패널", async () => {
    mockApi();
    const { router } = await renderRoute("/admin/academy/hrd?hrd=h1");
    const sheet = await screen.findByRole("dialog", { name: "백엔드 KDT" });
    expect(within(sheet).getByRole("region", { name: "훈련 정보" })).toHaveTextContent(
      "훈련 유형KDTNCS20 › 01 › 02주말·야간평일 · 주간총 훈련비11,200,000원시간당 훈련비12,000원총 훈련 시간960시간총 훈련 일수120일",
    );
    expect(within(sheet).getByRole("list", { name: "연결 운영과정" })).toHaveTextContent(
      "백엔드 부트캠프BECEO 과정CEO",
    );
    const rounds = await within(sheet).findByRole("list", { name: "회차" });
    const items = within(rounds).getAllByRole("link");
    expect(items.map((l) => l.textContent)).toEqual([
      "16회차2026.06.02 ~ 2026.11.30연결된 기수 없음",
      "15회차2026.06.02 ~ 2026.11.30백엔드 부트캠프 12기, CEO 과정 1기",
    ]);
    const user = userEvent.setup();
    await user.click(items[1]!);
    await waitFor(() => expect(router.state.location.search).toEqual({ hrd: "h1", cohort: "r15" }));
    expect(await screen.findByRole("dialog", { name: "15회차" })).toHaveTextContent("자부담금1,120,000원");
  });

  it("HRD 과정 수정: 숫자가 아니면 오류, 비운 값은 null로 보낸다", async () => {
    const { patches } = mockApi();
    await renderRoute("/admin/academy/hrd?hrd=h1");
    const sheet = await screen.findByRole("dialog", { name: "백엔드 KDT" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "수정" }));
    const form = within(sheet).getByRole("form", { name: "HRD 과정 수정" });
    const fee = within(form).getByRole("textbox", { name: "총 훈련비" });
    await user.clear(fee);
    await user.type(fee, "abc");
    await user.click(within(form).getByRole("button", { name: "저장" }));
    expect(await within(form).findByText("0 이상의 숫자만 적어 주세요.")).toBeInTheDocument();
    await user.clear(fee);
    await user.clear(within(form).getByRole("textbox", { name: "NCS 소분류" }));
    await user.click(within(form).getByRole("button", { name: "저장" }));
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0]).toMatchObject({
      path: "hrd",
      body: { total_train_fee: null, ncs3_se: null, name: "백엔드 KDT" },
    });
    expect(await screen.findByText("백엔드 KDT HRD 과정을 저장했어요")).toBeInTheDocument();
  });

  it("회차 자부담금 수정", async () => {
    const { patches } = mockApi();
    await renderRoute("/admin/academy/hrd?hrd=h1&cohort=r15");
    const sheet = await screen.findByRole("dialog", { name: "15회차" });
    const user = userEvent.setup();
    await user.click(within(sheet).getByRole("button", { name: "수정" }));
    const form = within(sheet).getByRole("form", { name: "회차 수정" });
    const pay = within(form).getByRole("textbox", { name: "자부담금" });
    await user.clear(pay);
    await user.type(pay, "900000");
    await user.click(within(form).getByRole("button", { name: "저장" }));
    await waitFor(() => expect(patches).toEqual([{ path: "cohort", body: { self_pay_amount: 900000 } }]));
    expect(await screen.findByText("백엔드 KDT 15회차를 저장했어요")).toBeInTheDocument();
  });

  it("조회 권한만 있으면 [수정]이 없다", async () => {
    mockApi({ codes: ["academy.hrd.read"] });
    await renderRoute("/admin/academy/hrd?hrd=h1");
    const sheet = await screen.findByRole("dialog", { name: "백엔드 KDT" });
    await within(sheet).findByRole("list", { name: "회차" });
    expect(within(sheet).queryByRole("button", { name: "수정" })).not.toBeInTheDocument();
  });
});
