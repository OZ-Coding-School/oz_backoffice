import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { requestKeys } from "@/features/requests/api";

/** 목록 카드 (신청 받는 멘토) */
export type MentorCard = components["schemas"]["MentorCard"];
/** 소개 모달 (단건) */
export type MentorProfile =
  components["schemas"]["app__contexts__mentoring__presentation__student_router__MentorProfileResponse"];
export type AvailableTimes = components["schemas"]["AvailableTimesResponse"];
export type StudentTeam = components["schemas"]["StudentTeamResponse"];

export const applyKeys = {
  mentors: (cohortId: string) => ["apply", "mentors", cohortId] as const,
  mentor: (cohortId: string, mentorId: string) => ["apply", "mentor", cohortId, mentorId] as const,
  times: (mentorId: string, cohortId: string, from: string, to: string) =>
    ["apply", "times", mentorId, cohortId, from, to] as const,
};

/** 내 팀 (수강생으로 속한 팀, A39) */
export const myTeamsQuery = queryOptions({
  queryKey: ["apply", "teams"] as const,
  queryFn: () => unwrap(api.GET("/api/v1/me/mentoring-teams")),
});

/** 신청 받는 멘토 (기수에 활성 배정, A64) */
export function mentorsQuery(cohortId: string) {
  return queryOptions({
    queryKey: applyKeys.mentors(cohortId),
    queryFn: () => unwrap(api.GET("/api/v1/me/mentoring/mentors", { params: { query: { cohort_id: cohortId } } })),
  });
}

/** 멘토 공개 프로필 단건 (소개 모달) */
export function mentorQuery(cohortId: string, mentorId: string) {
  return queryOptions({
    queryKey: applyKeys.mentor(cohortId, mentorId),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/me/mentoring/mentors/{mentor_id}", {
          params: { path: { mentor_id: mentorId }, query: { cohort_id: cohortId } },
        }),
      ),
  });
}

/** 멘토의 신청 가능 시간 (KST 날짜 from~to, 31일까지, A38) */
export function availableTimesQuery(mentorId: string, cohortId: string, from: string, to: string) {
  return queryOptions({
    queryKey: applyKeys.times(mentorId, cohortId, from, to),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/mentors/{mentor_id}/available-times", {
          params: { path: { mentor_id: mentorId }, query: { cohort_id: cohortId, from, to } },
        }),
      ),
  });
}

export type CreateInput = {
  topic: string;
  detail: string;
  desiredTimes: string[];
  duration: number;
} & ({ kind: "one"; cohortId: string; mentorId: string } | { kind: "team"; teamId: string });

export function useCreateRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateInput) =>
      unwrap(
        api.POST("/api/v1/mentoring/requests", {
          // 1:1은 기수·멘토, 팀은 팀만 보낸다 (담당 멘토는 서버가 정한다)
          body: {
            cohort_id: input.kind === "one" ? input.cohortId : null,
            mentor_id: input.kind === "one" ? input.mentorId : null,
            team_id: input.kind === "team" ? input.teamId : null,
            topic: input.topic,
            detail: input.detail,
            desired_times: input.desiredTimes,
            duration: input.duration,
          },
        }),
      ),
    onSuccess: (created) => {
      queryClient.setQueryData(requestKeys.detail(created.id), created);
      void queryClient.invalidateQueries({ queryKey: ["requests", "mine"] });
      void queryClient.invalidateQueries({ queryKey: requestKeys.balances });
      void queryClient.invalidateQueries({ queryKey: ["apply", "times"] });
    },
  });
}

/** 전문 분야: 쉼표로 나눈 칩 (F30) */
export function expertiseChips(expertise: string | null | undefined): string[] {
  return (expertise ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}
