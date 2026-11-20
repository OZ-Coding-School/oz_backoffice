import { formatKst, toEpochMs } from "@/lib/datetime";

import type { Artifact, MentoringSession, TranscriptEntry } from "./api";

/** 회의 하나의 녹화 묶음 (A69: 같은 conference_record의 영상·전사본·스마트 메모) */
export interface Recording {
  key: string;
  video: Artifact | null;
  transcript: Artifact | null;
  summary: Artifact | null;
  /** 녹화 시작 (영상의 started_at, 없으면 만든 시각) */
  startedAt: string | null;
  /** 녹화 끝 (A71). 없으면 시작만 보여 준다 */
  endedAt: string | null;
}

/** 영상이 있는 회의만, 녹화 시작 순으로 (F35) */
export function groupRecordings(artifacts: readonly Artifact[]): Recording[] {
  const groups = new Map<string, Recording>();
  for (const a of artifacts) {
    const key = a.conference_record ?? "";
    const g = groups.get(key) ?? { key, video: null, transcript: null, summary: null, startedAt: null, endedAt: null };
    if (a.artifact_type === "VIDEO" && !g.video) {
      g.video = a;
      g.startedAt = a.started_at ?? a.created_at;
      g.endedAt = a.ended_at;
    } else if (a.artifact_type === "TRANSCRIPT" && !g.transcript) g.transcript = a;
    else if (a.artifact_type === "SUMMARY" && !g.summary) g.summary = a;
    groups.set(key, g);
  }
  return [...groups.values()]
    .filter((g) => g.video)
    .sort((a, b) => (a.startedAt ? toEpochMs(a.startedAt) : 0) - (b.startedAt ? toEpochMs(b.startedAt) : 0));
}

/** "녹화 1 · 10:02 ~ 10:40" (끝을 모르면 시작만, A71) */
export function recordingLabel(recording: Pick<Recording, "startedAt" | "endedAt">, index: number): string {
  const name = `녹화 ${index + 1}`;
  if (!recording.startedAt) return name;
  const start = formatKst(recording.startedAt, "HH:mm");
  return recording.endedAt ? `${name} · ${start} ~ ${formatKst(recording.endedAt, "HH:mm")}` : `${name} · ${start}`;
}

/** 전사 문장의 영상 위치(초) = 문장 시각 − 녹화 시작 (A69). 녹화 시작을 모르면 null */
export function entryOffset(
  entry: Pick<TranscriptEntry, "started_at">,
  recordingStartedAt: string | null,
): number | null {
  if (!recordingStartedAt) return null;
  return Math.max(0, (toEpochMs(entry.started_at) - toEpochMs(recordingStartedAt)) / 1000);
}

/** 재생 위치에 해당하는 문장 순번 (시작이 지난 마지막 문장) */
export function activeEntryIndex(offsets: readonly (number | null)[], current: number): number {
  let found = -1;
  offsets.forEach((o, i) => {
    if (o !== null && o <= current) found = i;
  });
  return found;
}

/** 초 → "12:40", 1시간 넘으면 "1:02:03" */
export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(Number.isFinite(totalSeconds) ? totalSeconds : 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${String(m).padStart(2, "0")}:${sec}`;
}

const COLLECT_DAYS = 7;

/** 녹화가 없을 때 안내 (F35): 종료 후 7일 안이면 정리 중, 지나면 없음 */
export function missingRecordingState(
  session: Pick<MentoringSession, "actual_ended_at" | "ends_at">,
  now: Date,
): "processing" | "none" {
  const ended = toEpochMs(session.actual_ended_at ?? session.ends_at);
  return now.getTime() - ended < COLLECT_DAYS * 86_400_000 ? "processing" : "none";
}
