import { http, HttpResponse } from "msw";

import { apiUrl } from "@/mocks/api";
import { server } from "@/mocks/node";

import type { MentoringRequest, RequestCounts } from "./api";

/** 수강 등록 st12(가수강, ENROLLMENTS)의 1:1 신청 */
export function makeRequest(overrides: Partial<MentoringRequest> = {}): MentoringRequest {
  return {
    id: "r1",
    status: "PENDING",
    team_id: null,
    team_label: null,
    requester_id: "st12",
    requester_name: "가수강",
    mentor_id: "m1",
    mentor_display_name: "멘토K",
    mentor_headline: "네이버 백엔드 7년차",
    topic: "Django ORM 질문",
    detail: "## 질문 정리\n\n- select_related와 prefetch_related\n",
    desired_times: ["2026-11-24T10:00:00Z", "2026-11-25T10:00:00Z"],
    duration: 60,
    reject_reason: null,
    rejected_at: null,
    cancel_reason: null,
    canceled_at: null,
    canceled_by: null,
    session: null,
    balance: { state: "HELD", minutes: 60 },
    replaced_request_id: null,
    created_at: "2026-11-16T01:02:00Z",
    ...overrides,
  };
}

export const COUNTS: RequestCounts = { PENDING: 1, APPROVED: 1, REJECTED: 0, CANCELED: 1 };

/** 목록: status 쿼리로 거르고, offset·limit으로 나눈다 */
export function mockRequestList(items: MentoringRequest[], counts: RequestCounts = COUNTS) {
  const seen: { status: string[]; offset: number }[] = [];
  server.use(
    http.get(apiUrl("/api/v1/me/mentoring/requests"), ({ request }) => {
      const url = new URL(request.url);
      const status = url.searchParams.getAll("status");
      const offset = Number(url.searchParams.get("offset") ?? 0);
      const limit = Number(url.searchParams.get("limit") ?? 20);
      seen.push({ status, offset });
      const found = items.filter((r) => status.length === 0 || status.includes(r.status));
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

export function mockRequestDetail(request: MentoringRequest) {
  server.use(http.get(apiUrl("/api/v1/mentoring/requests/{request_id}"), () => HttpResponse.json(request)));
}

export function mockBalances(remaining = 120) {
  server.use(
    http.get(apiUrl("/api/v1/me/balances"), () =>
      HttpResponse.json([
        {
          id: "a1",
          owner_type: "STUDENT",
          owner_id: "st12",
          owner_name: "가수강",
          valid_from: "2026-10-01",
          valid_until: "2027-03-31",
          is_expired: false,
          total_minutes: 180,
          held_minutes: 60,
          used_minutes: 0,
          remaining_minutes: remaining,
        },
      ]),
    ),
  );
}

export function mockSettings(minLeadHours = 24) {
  server.use(
    http.get(apiUrl("/api/v1/me/mentoring/settings"), () =>
      HttpResponse.json({
        cohort_id: "c12",
        allow_1_on_1: true,
        allow_team_mentoring: true,
        allowed_duration: 30,
        min_lead_hours: minLeadHours,
        max_pending_requests: 3,
      }),
    ),
  );
}
