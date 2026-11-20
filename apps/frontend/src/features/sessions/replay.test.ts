import {
  activeEntryIndex,
  entryOffset,
  formatClock,
  groupRecordings,
  missingRecordingState,
  recordingLabel,
} from "./replay";
import { ARTIFACTS, makeArtifact, makeCompleted } from "./test-utils";

describe("다시 보기 규칙 (F35·A69·A71)", () => {
  it("회의 기록별로 영상·전사본·스마트 메모를 묶고, 영상이 있는 회의만 녹화 시작 순으로 둔다", () => {
    const orphan = makeArtifact({ id: "t9", artifact_type: "TRANSCRIPT", conference_record: "c9" });
    const recordings = groupRecordings([ARTIFACTS[3]!, orphan, ...ARTIFACTS.slice(0, 3), ARTIFACTS[4]!]);
    expect(recordings.map((r) => [r.key, r.video?.id, r.transcript?.id, r.summary?.id ?? null])).toEqual([
      ["c1", "v1", "t1", "n1"],
      ["c2", "v2", "t2", null],
    ]);
  });

  it("녹화 이름은 시작 ~ 끝, 끝을 모르면 시작만", () => {
    const [first] = groupRecordings(ARTIFACTS);
    expect(recordingLabel(first!, 0)).toBe("녹화 1 · 10:02 ~ 10:40");
    expect(recordingLabel({ startedAt: "2026-11-16T01:41:00Z", endedAt: null }, 1)).toBe("녹화 2 · 10:41");
    expect(recordingLabel({ startedAt: null, endedAt: null }, 2)).toBe("녹화 3");
  });

  it("문장 위치 = 문장 시각 − 녹화 시작, 재생 위치에 맞는 문장을 고른다", () => {
    const start = "2026-11-16T01:02:00Z";
    expect(entryOffset({ started_at: "2026-11-16T01:04:40Z" }, start)).toBe(160);
    expect(entryOffset({ started_at: "2026-11-16T01:01:00Z" }, start)).toBe(0);
    expect(entryOffset({ started_at: "2026-11-16T01:04:40Z" }, null)).toBeNull();
    expect(activeEntryIndex([10, 20, null, 30], 5)).toBe(-1);
    expect(activeEntryIndex([10, 20, null, 30], 20)).toBe(1);
    expect(activeEntryIndex([10, 20, null, 30], 99)).toBe(3);
  });

  it("시각 표시", () => {
    expect(formatClock(0)).toBe("00:00");
    expect(formatClock(760.9)).toBe("12:40");
    expect(formatClock(3723)).toBe("1:02:03");
    expect(formatClock(Number.NaN)).toBe("00:00");
  });

  it("녹화가 없으면 종료 7일 안은 정리 중, 지나면 없음", () => {
    const session = makeCompleted(); // 실제 종료 11/16 02:01Z
    expect(missingRecordingState(session, new Date("2026-11-23T02:00:00Z"))).toBe("processing");
    expect(missingRecordingState(session, new Date("2026-11-23T02:02:00Z"))).toBe("none");
  });
});
