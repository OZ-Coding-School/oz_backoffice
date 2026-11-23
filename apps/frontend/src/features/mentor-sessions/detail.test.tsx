import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import type { MentoringSession } from "@/features/sessions/api";
import { makeSession } from "@/features/sessions/test-utils";
import { apiUrl, errorBody } from "@/mocks/api";
import { server } from "@/mocks/node";
import { renderRoute } from "@/test/render";

import { durationOptions } from "./schemas";

const MENTOR = makeMe({
  id: "u9",
  name: "김멘토",
  account_type: "MENTOR",
  roles: [{ role: "MENTOR", scope_type: "GLOBAL", scope_id: null, expires_at: null }],
});

const NOW = new Date("2026-11-20T08:00:00Z"); // 11/20(금) 17:00 KST
// 11/20 14:00~15:00 KST, 진행됐고 기록 없음, Meet 15:02~16:31
const MISSING = makeSession({
  topic: "ORM 최적화",
  actual_started_at: "2026-11-20T06:02:00Z",
  actual_ended_at: "2026-11-20T07:31:00Z",
});

function mockSession(session: MentoringSession) {
  server.use(
    http.get(apiUrl("/api/v1/mentoring/sessions/{session_id}"), () => HttpResponse.json(session)),
    http.get(apiUrl("/api/v1/mentoring/sessions/{session_id}/note"), () =>
      HttpResponse.json({ session_id: session.id, body: null, updated_at: null }),
    ),
  );
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(NOW);
  resetAuth();
  mockSignedIn(MENTOR);
});

afterEach(() => vi.useRealTimers());

describe("진행 시간 보기 (F48)", () => {
  it("30분부터 신청 +120분까지 30분 단위", () => {
    expect(durationOptions(60)).toEqual([30, 60, 90, 120, 150, 180]);
  });
});

describe("멘토 세션 상세·기록 (F48·A78)", () => {
  it("기록 미제출이면 머리·신청 정보·작성 폼을 보여 주고, 길게 진행하면 초과 안내 뒤 제출한다", async () => {
    mockSession(MISSING);
    const posted: unknown[] = [];
    server.use(
      http.post(apiUrl("/api/v1/mentoring/sessions/{session_id}/record"), async ({ request }) => {
        const body = (await request.json()) as { duration: number; topic: string; summary: string };
        posted.push(body);
        return HttpResponse.json({
          ...MISSING,
          status: "COMPLETED",
          record_duration_minutes: body.duration,
          topic: body.topic,
          summary: body.summary,
          recorded_at: NOW.toISOString(),
        });
      }),
    );
    await renderRoute("/mentor/sessions/s1");

    expect(await screen.findByRole("heading", { name: "멘토K 멘토링 3회차", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("기록 미제출")).toBeInTheDocument();
    expect(screen.getByText("11/20(금) 14:00 ~ 15:00 · 가수강 · 1:1 · 초격차 백엔드 12기")).toBeInTheDocument();
    expect(screen.getByText("15:02 ~ 16:31 · 89분")).toBeInTheDocument(); // Meet 기록 참고
    const info = screen.getByRole("region", { name: "신청 정보" });
    expect(within(info).getByText("60분")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("combobox", { name: "실제 진행 시간" }));
    await user.click(await screen.findByRole("option", { name: "90분" }));
    expect(screen.getByText("신청보다 30분 길게 진행했어요")).toBeInTheDocument();
    expect(screen.getByText(/차감하지 못한 시간은 운영진이 정산할 때 참고해요/)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "주제" })).toHaveValue("ORM 최적화");

    await user.click(screen.getByRole("button", { name: "기록 제출" }));
    expect(await screen.findByText("요약을 적어 주세요.")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "요약 (수강생도 봐요)" }), "N+1 줄이기");
    await user.click(screen.getByRole("tab", { name: "미리보기" }));
    expect(within(screen.getByLabelText("미리보기")).getByText("N+1 줄이기")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "기록 제출" }));

    const record = await screen.findByRole("region", { name: "세션 기록" });
    await waitFor(() => expect(within(record).getByText("진행함 · 90분 (고정)")).toBeInTheDocument());
    expect(posted).toEqual([{ status: "COMPLETED", duration: 90, topic: "ORM 최적화", summary: "N+1 줄이기" }]);
  });

  it("노쇼는 사유만 받고, 짧게 진행하면 돌려드린다고 안내한다", async () => {
    mockSession(MISSING);
    const posted: unknown[] = [];
    server.use(
      http.post(apiUrl("/api/v1/mentoring/sessions/{session_id}/record"), async ({ request }) => {
        posted.push(await request.json());
        return HttpResponse.json({ ...MISSING, status: "NO_SHOW", recorded_at: NOW.toISOString() });
      }),
    );
    await renderRoute("/mentor/sessions/s1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("combobox", { name: "실제 진행 시간" }));
    await user.click(await screen.findByRole("option", { name: "30분" }));
    expect(screen.getByText("신청보다 30분 짧게 진행했어요")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "노쇼 (수강생이 들어오지 않음)" }));
    expect(screen.queryByRole("combobox", { name: "실제 진행 시간" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "기록 제출" }));
    await waitFor(() => expect(posted).toEqual([{ status: "NO_SHOW", summary: null }]));
    expect(await screen.findByText("노쇼 (고정)")).toBeInTheDocument();
  });

  it("제출한 기록은 7일 안에 주제·요약만 같은 카드에서 고친다", async () => {
    const done = makeSession({
      ...MISSING,
      status: "COMPLETED",
      record_duration_minutes: 90,
      summary: "## 오늘 다룬 것",
      recorded_at: "2026-11-20T08:00:00Z",
    });
    mockSession(done);
    const patched: unknown[] = [];
    server.use(
      http.patch(apiUrl("/api/v1/mentoring/sessions/{session_id}/record"), async ({ request }) => {
        const body = (await request.json()) as { topic: string; summary: string };
        patched.push(body);
        return HttpResponse.json({ ...done, ...body });
      }),
    );
    await renderRoute("/mentor/sessions/s1");
    const record = await screen.findByRole("region", { name: "세션 기록" });
    expect(within(record).getByText("11/27까지 수정 가능")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(within(record).getByRole("button", { name: "수정" }));
    expect(screen.getByText("진행함 · 90분 (고정) · 11/27까지 고칠 수 있어요")).toBeInTheDocument();
    const topic = screen.getByRole("textbox", { name: "주제" });
    await user.clear(topic);
    await user.type(topic, "ORM 심화");
    await user.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(patched).toEqual([{ topic: "ORM 심화", summary: "## 오늘 다룬 것" }]));
    expect(await screen.findByText("ORM 심화")).toBeInTheDocument();
  });

  it("7일이 지나면 수정 버튼 대신 기한을 알린다", async () => {
    mockSession(
      makeSession({
        ...MISSING,
        status: "COMPLETED",
        record_duration_minutes: 60,
        recorded_at: "2026-11-10T08:00:00Z",
      }),
    );
    await renderRoute("/mentor/sessions/s1");
    expect(await screen.findByText("11/17까지 수정할 수 있었어요")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "수정" })).not.toBeInTheDocument();
  });

  it("시작 전이면 안내하고 오늘이면 Meet 입장을 보여 준다", async () => {
    mockSession(makeSession({ starts_at: "2026-11-20T09:00:00Z", ends_at: "2026-11-20T10:00:00Z" }));
    await renderRoute("/mentor/sessions/s1");
    expect(await screen.findByText(/11\/20\(금\) 18:00 시작 후 기록할 수 있어요/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Meet 입장" })).toHaveAttribute(
      "href",
      "https://meet.google.com/abc-defg-hij",
    );
    expect(screen.queryByRole("button", { name: "기록 제출" })).not.toBeInTheDocument();
  });

  it("취소된 세션은 사유를 보여 준다", async () => {
    mockSession(
      makeSession({
        status: "CANCELED",
        cancel_reason: "개인 일정으로 참석이 어려워요",
        canceled_by: "REQUESTER",
        canceled_at: "2026-11-18T12:40:00Z",
        balance: { state: "RETURNED", minutes: 60 },
      }),
    );
    await renderRoute("/mentor/sessions/s1");
    const card = await screen.findByRole("region", { name: "취소된 세션이에요" });
    expect(card).toHaveTextContent("취소 사유 · 개인 일정으로 참석이 어려워요");
  });

  it("내부 메모를 저장한다", async () => {
    mockSession(MISSING);
    const saved: unknown[] = [];
    server.use(
      http.put(apiUrl("/api/v1/mentoring/sessions/{session_id}/note"), async ({ request }) => {
        const body = (await request.json()) as { body: string };
        saved.push(body);
        return HttpResponse.json({ session_id: "s1", body: body.body, updated_at: NOW.toISOString() });
      }),
    );
    await renderRoute("/mentor/sessions/s1");
    const user = userEvent.setup();
    const box = await screen.findByRole("textbox", { name: "내부 메모" });
    expect(screen.getByRole("button", { name: "메모 저장" })).toBeDisabled();
    await user.type(box, "다음엔 SQL 기초 자료 먼저");
    await user.click(screen.getByRole("button", { name: "메모 저장" }));
    await waitFor(() => expect(saved).toEqual([{ body: "다음엔 SQL 기초 자료 먼저" }]));
    expect(await screen.findByText("11/20(금) 17:00 저장")).toBeInTheDocument();
  });

  it("기록 제출 오류는 문구로 안내한다", async () => {
    mockSession(MISSING);
    server.use(
      http.post(apiUrl("/api/v1/mentoring/sessions/{session_id}/record"), () =>
        HttpResponse.json(errorBody("session_not_started"), { status: 422 }),
      ),
    );
    await renderRoute("/mentor/sessions/s1");
    const user = userEvent.setup();
    await user.type(await screen.findByRole("textbox", { name: "요약 (수강생도 봐요)" }), "요약");
    await user.click(screen.getByRole("button", { name: "기록 제출" }));
    expect(await screen.findByText("세션이 시작된 뒤에 기록할 수 있어요.")).toBeInTheDocument();
  });
});
