import { http, HttpResponse } from "msw";

import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";

import type { Artifact, MentoringSession, SessionCounts, TranscriptEntry } from "./api";

/** 수강 등록 st12(가수강, ENROLLMENTS)의 1:1 세션 (예정, 11/20 14:00~15:00 KST) */
export function makeSession(overrides: Partial<MentoringSession> = {}): MentoringSession {
  return {
    id: "s1",
    status: "SCHEDULED",
    title: "멘토K 멘토링 3회차",
    topic: "포트폴리오 리뷰와 README 구성",
    detail: "README에 아키텍처 그림을 넣는 게 좋을지 궁금해요.",
    starts_at: "2026-11-20T05:00:00Z",
    ends_at: "2026-11-20T06:00:00Z",
    request_id: "r1",
    team_id: null,
    team_label: null,
    requester_id: "st12",
    requester_name: "가수강",
    mentor_id: "m1",
    mentor_display_name: "멘토K",
    mentor_headline: "네이버 백엔드 7년차",
    participants: [{ student_id: "st12", name: "가수강" }],
    actual_started_at: null,
    actual_ended_at: null,
    cancel_reason: null,
    canceled_by: null,
    canceled_at: null,
    balance: { state: "HELD", minutes: 60 },
    approved_rank: 1,
    requested_at: "2026-11-14T13:30:00Z",
    google_meet_url: "https://meet.google.com/abc-defg-hij",
    summary: null,
    record_duration_minutes: null,
    recorded_at: null,
    created_at: "2026-11-14T13:40:00Z",
    ...overrides,
  };
}

/** 완료 세션 (11/16 10:02~11:01 실제, 기록 60분, 1시간 차감) */
export function makeCompleted(overrides: Partial<MentoringSession> = {}): MentoringSession {
  return makeSession({
    id: "s2",
    status: "COMPLETED",
    title: "멘토K 멘토링 2회차",
    topic: "README 구성",
    starts_at: "2026-11-16T01:00:00Z",
    ends_at: "2026-11-16T02:00:00Z",
    actual_started_at: "2026-11-16T01:02:00Z",
    actual_ended_at: "2026-11-16T02:01:00Z",
    balance: { state: "USED", minutes: 60 },
    google_meet_url: null,
    summary: "## 오늘 다룬 것\n\n- README 첫 화면에 서비스 한 줄 소개 넣기\n",
    record_duration_minutes: 60,
    recorded_at: "2026-11-16T02:20:00Z",
    ...overrides,
  });
}

export const COUNTS: SessionCounts = { SCHEDULED: 1, IN_PROGRESS: 0, COMPLETED: 2, NO_SHOW: 1, CANCELED: 1 };

/** 목록: status 쿼리로 거르고, offset·limit으로 나눈다 */
export function mockSessionList(items: MentoringSession[], counts: SessionCounts = COUNTS) {
  const seen: { status: string[]; offset: number }[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/mentoring/sessions"), ({ request }) => {
      const url = new URL(request.url);
      const status = url.searchParams.getAll("status");
      const offset = Number(url.searchParams.get("offset") ?? 0);
      const limit = Number(url.searchParams.get("limit") ?? 20);
      seen.push({ status, offset });
      const found = items.filter((s) => status.length === 0 || status.includes(s.status));
      return HttpResponse.json({
        items: found.slice(offset, offset + limit),
        total: found.length,
        limit,
        offset,
        counts,
      });
    }),
  );
  return seen;
}

export function mockSessionDetail(session: MentoringSession) {
  server.use(http.get(apiUrl("/api/v1/mentoring/sessions/{session_id}"), () => HttpResponse.json(session)));
}

/** 회의 c1·c2의 영상·전사본과 c1 스마트 메모 (완료 세션 s2, 10:02~10:40 / 10:41~11:01 KST) */
export const ARTIFACTS: Artifact[] = [
  makeArtifact({
    id: "v1",
    artifact_type: "VIDEO",
    conference_record: "c1",
    started_at: "2026-11-16T01:02:00Z",
    ended_at: "2026-11-16T01:40:00Z",
  }),
  makeArtifact({ id: "t1", artifact_type: "TRANSCRIPT", conference_record: "c1" }),
  makeArtifact({ id: "n1", artifact_type: "SUMMARY", conference_record: "c1" }),
  makeArtifact({
    id: "v2",
    artifact_type: "VIDEO",
    conference_record: "c2",
    started_at: "2026-11-16T01:41:00Z",
    ended_at: "2026-11-16T02:01:00Z",
  }),
  makeArtifact({ id: "t2", artifact_type: "TRANSCRIPT", conference_record: "c2" }),
];

export function makeArtifact(overrides: Partial<Artifact> & Pick<Artifact, "id" | "artifact_type">): Artifact {
  return {
    file_name: null,
    mime_type: overrides.artifact_type === "VIDEO" ? "video/mp4" : "application/pdf",
    file_size: null,
    conference_record: null,
    started_at: null,
    ended_at: null,
    created_at: "2026-11-16T02:10:00Z",
    ...overrides,
  };
}

/** 녹화 목록·서명 링크·전사 문장·스마트 메모 */
export function mockArtifacts(
  artifacts: Artifact[] = ARTIFACTS,
  entries: Record<string, TranscriptEntry[]> = {},
  markdown = "## 요약\n\n- README 첫 화면 정리",
) {
  const linked: string[] = [];
  server.use(
    http.get(apiUrl("/api/v1/mentoring/sessions/{session_id}/artifacts"), () => HttpResponse.json(artifacts)),
    http.post(apiUrl("/api/v1/mentoring/sessions/{session_id}/artifacts/{artifact_id}/link"), ({ params }) => {
      const id = String(params.artifact_id);
      linked.push(id);
      const path = `/api/v1/mentoring/artifacts/${id}/stream?token=tk`;
      return HttpResponse.json({ url: path, download_url: `${path}&download=1`, expires_at: "2026-11-16T05:00:00Z" });
    }),
    http.get(apiUrl("/api/v1/mentoring/sessions/{session_id}/artifacts/{artifact_id}/entries"), ({ params }) =>
      HttpResponse.json(entries[String(params.artifact_id)] ?? []),
    ),
    http.get(apiUrl("/api/v1/mentoring/sessions/{session_id}/artifacts/{artifact_id}/markdown"), ({ params }) =>
      HttpResponse.json({ artifact_id: String(params.artifact_id), markdown }),
    ),
  );
  return linked;
}
