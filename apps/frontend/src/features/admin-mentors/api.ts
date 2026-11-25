import { infiniteQueryOptions, queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { postPhoto, type MentorProfile, type PhotoChange, type ProfileUpdate } from "@/features/mentor-profile/api";

export type MentorItem = components["schemas"]["MentorListItem"];
export type MentorAssignment = components["schemas"]["MyAssignmentResponse"];
export type Deactivation = components["schemas"]["MentorDeactivationResponse"];
export type Activation = components["schemas"]["MentorActivationResponse"];

export const PAGE_SIZE = 20;

export interface MentorFilter {
  q?: string;
  status?: "active" | "inactive";
}

export const mentorKeys = {
  all: ["admin-mentors"] as const,
  list: (f: MentorFilter) => ["admin-mentors", "list", f.q ?? "", f.status ?? ""] as const,
  detail: (id: string) => ["admin-mentors", "detail", id] as const,
  profile: (id: string) => ["admin-mentors", "profile", id] as const,
  assignments: (id: string) => ["admin-mentors", "assignments", id] as const,
};

/** 멘토 목록 (A100). 20개씩 이어 붙인다 */
export function mentorsQuery(f: MentorFilter) {
  return infiniteQueryOptions({
    queryKey: mentorKeys.list(f),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/admin/mentors", {
          params: {
            query: {
              limit: PAGE_SIZE,
              offset: pageParam,
              ...(f.q ? { q: f.q } : {}),
              ...(f.status ? { is_active: f.status === "active" } : {}),
            },
          },
        }),
      ),
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.limit : undefined),
  });
}

/** 멘토 하나 (A102): 머리·계정 칸 */
export function mentorQuery(id: string) {
  return queryOptions({
    queryKey: mentorKeys.detail(id),
    queryFn: () => unwrap(api.GET("/api/v1/admin/mentors/{mentor_id}", { params: { path: { mentor_id: id } } })),
  });
}

export function mentorProfileQuery(id: string) {
  return queryOptions({
    queryKey: mentorKeys.profile(id),
    queryFn: () =>
      unwrap(api.GET("/api/v1/admin/mentors/{mentor_id}/profile", { params: { path: { mentor_id: id } } })),
  });
}

/** 그 멘토의 기수 배정 전체 (A101): 비활성 포함, 활성 먼저 */
export function mentorAssignmentsQuery(id: string) {
  return queryOptions({
    queryKey: mentorKeys.assignments(id),
    queryFn: () =>
      unwrap(api.GET("/api/v1/admin/mentors/{mentor_id}/mentor-assignments", { params: { path: { mentor_id: id } } })),
  });
}

/** 바뀐 멘토의 상세·목록·배정을 다시 읽는다 */
function useRefresh(id: string) {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: mentorKeys.detail(id) });
    void client.invalidateQueries({ queryKey: mentorKeys.assignments(id) });
    void client.invalidateQueries({ queryKey: ["admin-mentors", "list"] });
  };
}

/** 운영진 대리 수정 (F79): 글 입력 먼저, 사진은 그다음. 바뀐 것만 보낸다 */
export function useSaveProfile(id: string) {
  const client = useQueryClient();
  const refresh = useRefresh(id);
  const path = { params: { path: { mentor_id: id } } };
  return useMutation({
    mutationFn: async ({ body, photo }: { body: ProfileUpdate | null; photo: PhotoChange }) => {
      let profile: MentorProfile | null = null;
      if (body) profile = await unwrap(api.PATCH("/api/v1/admin/mentors/{mentor_id}/profile", { ...path, body }));
      if (photo.kind === "replace") {
        const ticket = await unwrap(
          api.POST("/api/v1/admin/mentors/{mentor_id}/profile/image/uploads", {
            ...path,
            body: { content_type: "image/webp" },
          }),
        );
        await postPhoto(ticket, photo.image);
        profile = await unwrap(
          api.POST("/api/v1/admin/mentors/{mentor_id}/profile/image/uploads/{upload_id}/confirm", {
            params: { path: { mentor_id: id, upload_id: ticket.upload_id } },
          }),
        );
      }
      if (photo.kind === "remove")
        profile = await unwrap(api.DELETE("/api/v1/admin/mentors/{mentor_id}/profile/image", path));
      return profile;
    },
    onSettled: (profile) => {
      if (profile) client.setQueryData(mentorKeys.profile(id), profile);
      else void client.invalidateQueries({ queryKey: mentorKeys.profile(id) });
      refresh();
    },
  });
}

/** 신청 받기 켜기·끄기 (A37) */
export function useSetAccepting(id: string) {
  const refresh = useRefresh(id);
  return useMutation({
    mutationFn: (accepting: boolean) =>
      unwrap(
        api.PUT("/api/v1/admin/mentors/{mentor_id}/schedule/accepting", {
          params: { path: { mentor_id: id } },
          body: { accepting_requests: accepting },
        }),
      ),
    onSettled: refresh,
  });
}

/** 비활성화 (A35): confirm=false면 미리보기(함께 꺼질 배정·취소될 대기 신청 수)만 */
export function useDeactivate(id: string) {
  const refresh = useRefresh(id);
  return useMutation({
    mutationFn: (confirm: boolean) =>
      unwrap(
        api.POST("/api/v1/admin/mentors/{mentor_id}/deactivate", {
          params: { path: { mentor_id: id } },
          body: { confirm },
        }),
      ),
    onSuccess: (res) => (res.applied ? refresh() : undefined),
  });
}

/** 활성화 (A35): 응답의 `restorable`이 다시 켤 배정 후보 */
export function useActivate(id: string) {
  const refresh = useRefresh(id);
  return useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/v1/admin/mentors/{mentor_id}/activate", { params: { path: { mentor_id: id } } })),
    onSuccess: refresh,
  });
}

/** 고른 배정을 다시 켠다 */
export function useReactivate(id: string) {
  const refresh = useRefresh(id);
  return useMutation({
    mutationFn: (ids: string[]) =>
      unwrap(
        api.POST("/api/v1/admin/mentors/{mentor_id}/mentor-assignments/reactivate", {
          params: { path: { mentor_id: id } },
          body: { assignment_ids: ids },
        }),
      ),
    onSettled: refresh,
  });
}
