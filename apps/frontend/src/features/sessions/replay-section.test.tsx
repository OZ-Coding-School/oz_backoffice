import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { makeMe, mockSignedIn, resetAuth } from "@/features/auth/test-utils";
import { env } from "@/env";
import { renderRoute } from "@/test/render";

import { ARTIFACTS, makeCompleted, mockArtifacts, mockSessionDetail } from "./test-utils";

const ENTRIES = {
  t1: [
    { sequence: 0, speaker_name: "멘토K", text: "README부터 봐요", started_at: "2026-11-16T01:04:40Z", ended_at: null },
    {
      sequence: 1,
      speaker_name: "가수강",
      text: "설치 방법이 길어요",
      started_at: "2026-11-16T01:14:18Z",
      ended_at: null,
    },
  ],
  t2: [
    {
      sequence: 0,
      speaker_name: "멘토K",
      text: "두 번째 회의예요",
      started_at: "2026-11-16T01:42:00Z",
      ended_at: null,
    },
  ],
};

const stream = (id: string) => `${env.backendUrl}/api/v1/mentoring/artifacts/${id}/stream?token=tk`;

beforeEach(() => {
  resetAuth();
  mockSignedIn(makeMe());
  // jsdom은 재생을 구현하지 않는다: 재생·일시정지 이벤트만 흉내 낸다
  vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(function (this: HTMLMediaElement) {
    this.dispatchEvent(new Event("play"));
    return Promise.resolve();
  });
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(function (this: HTMLMediaElement) {
    this.dispatchEvent(new Event("pause"));
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

function videoEl(): HTMLVideoElement {
  const el = document.querySelector("video");
  if (!el) throw new Error("video 없음");
  return el;
}

describe("다시 보기 (F35)", () => {
  it("영상·내려받기·전사 문장: 문장을 누르면 그 위치로 가고 재생 중인 문장을 강조한다", async () => {
    mockSessionDetail(makeCompleted());
    mockArtifacts(ARTIFACTS, ENTRIES);
    const user = userEvent.setup();
    await renderRoute("/mentoring/sessions/s2");

    const replay = await screen.findByRole("region", { name: "다시 보기" });
    await waitFor(() => expect(videoEl()).toHaveAttribute("src", stream("v1")));
    expect(within(replay).getByRole("link", { name: "내려받기" })).toHaveAttribute(
      "href",
      `${stream("v1")}&download=1`,
    );
    expect(within(replay).getByText("전사본·스마트 메모 정리됨")).toBeInTheDocument();

    const line = await within(replay).findByRole("button", { name: /02:40.*README부터 봐요/ });
    await user.click(line);
    expect(videoEl().currentTime).toBe(160);
    expect(line).toHaveAttribute("aria-current", "true");
    expect(within(replay).getByRole("button", { name: "일시정지" })).toBeInTheDocument();

    videoEl().currentTime = 740;
    fireEvent.timeUpdate(videoEl());
    expect(within(replay).getByRole("button", { name: /12:18.*설치 방법이 길어요/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(line).not.toHaveAttribute("aria-current");
    expect(within(replay).getByRole("link", { name: "PDF로 보기" })).toHaveAttribute("href", stream("t1"));
  }, 20_000); // 여러 화면을 지나는 긴 흐름 (전체 실행 부하에서 5초를 넘긴 적이 있다)

  it("회의가 여럿이면 녹화를 골라 영상·전사본을 함께 바꾼다", async () => {
    mockSessionDetail(makeCompleted());
    mockArtifacts(ARTIFACTS, ENTRIES);
    const user = userEvent.setup();
    await renderRoute("/mentoring/sessions/s2");

    const picker = await screen.findByRole("radiogroup", { name: "녹화 고르기" });
    expect(within(picker).getByRole("radio", { name: "녹화 1 · 10:02 ~ 10:40" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await user.click(within(picker).getByRole("radio", { name: "녹화 2 · 10:41 ~ 11:01" }));
    await waitFor(() => expect(videoEl()).toHaveAttribute("src", stream("v2")));
    expect(await screen.findByText("두 번째 회의예요")).toBeInTheDocument();

    // 두 번째 회의에는 스마트 메모가 없다
    await user.click(screen.getByRole("tab", { name: "스마트 메모" }));
    expect(screen.getByText("스마트 메모를 정리하고 있어요")).toBeInTheDocument();
  });

  it("스마트 메모 탭은 마크다운과 원본 PDF를 보여 준다", async () => {
    mockSessionDetail(makeCompleted());
    mockArtifacts(ARTIFACTS, ENTRIES);
    const user = userEvent.setup();
    await renderRoute("/mentoring/sessions/s2");
    await user.click(await screen.findByRole("tab", { name: "스마트 메모" }));
    expect(await screen.findByRole("heading", { name: "요약" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("link", { name: "PDF로 보기" })).toHaveAttribute("href", stream("n1")));
  });

  it("플레이어: 스페이스·화살표, 재생 속도, 소리", async () => {
    mockSessionDetail(makeCompleted());
    mockArtifacts(ARTIFACTS, ENTRIES);
    const user = userEvent.setup();
    await renderRoute("/mentoring/sessions/s2");
    const player = await screen.findByRole("group", { name: "녹화 플레이어" });
    await waitFor(() => expect(videoEl()).toHaveAttribute("src", stream("v1")));
    Object.defineProperty(videoEl(), "duration", { configurable: true, value: 3480 });
    fireEvent.loadedMetadata(videoEl());
    expect(within(player).getByText("00:00 / 58:00")).toBeInTheDocument();

    player.focus();
    await user.keyboard(" ");
    expect(within(player).getByRole("button", { name: "일시정지" })).toBeInTheDocument();
    await user.keyboard("{ArrowRight}{ArrowRight}");
    expect(videoEl().currentTime).toBe(10);
    await user.keyboard("{ArrowLeft}");
    expect(videoEl().currentTime).toBe(5);

    await user.click(within(player).getByRole("button", { name: "재생 속도 1배" }));
    await user.click(await screen.findByRole("menuitem", { name: "1.5×" }));
    expect(videoEl().playbackRate).toBe(1.5);
    expect(within(player).getByRole("button", { name: "재생 속도 1.5배" })).toBeInTheDocument();

    await user.click(within(player).getByRole("button", { name: "소리 끄기" }));
    expect(videoEl().muted).toBe(true);
    expect(within(player).getByRole("button", { name: "소리 켜기" })).toBeInTheDocument();
  });

  it("녹화가 아직 없으면 정리 중 안내를 보여 준다", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-16T03:00:00Z"));
    mockSessionDetail(makeCompleted());
    mockArtifacts([]);
    await renderRoute("/mentoring/sessions/s2");
    expect(await screen.findByText("녹화를 정리하고 있어요")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "내려받기" })).not.toBeInTheDocument();
    vi.useRealTimers();
  });

  it("종료 7일이 지나도 녹화가 없으면 없다고 알려 준다", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-12-01T00:00:00Z"));
    mockSessionDetail(makeCompleted());
    mockArtifacts([]);
    await renderRoute("/mentoring/sessions/s2");
    expect(await screen.findByText("이 세션은 녹화가 없어요")).toBeInTheDocument();
    vi.useRealTimers();
  });
});
