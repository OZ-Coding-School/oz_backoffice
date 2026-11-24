import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type MentorProfile =
  components["schemas"]["app__contexts__educator__presentation__mentor_router__MentorProfileResponse"];
export type ProfileUpdate = components["schemas"]["ProfileUpdate"];

export const mentorProfileKeys = {
  profile: ["mentor-profile"] as const,
};

/** 내 멘토 프로필 (A28) */
export const mentorProfileQuery = queryOptions({
  queryKey: mentorProfileKeys.profile,
  queryFn: () => unwrap(api.GET("/api/v1/me/mentor-profile")),
});

/** 사진 변경: 그대로 · 새 사진(브라우저가 줄인 WebP) · 지우기 */
export type PhotoChange = { kind: "keep" } | { kind: "replace"; image: Blob } | { kind: "remove" };

export class PhotoUploadError extends Error {
  constructor() {
    super("사진을 올리지 못했어요.");
    this.name = "PhotoUploadError";
  }
}

/** 업로드 표(A28)로 S3에 바로 올린다. fields를 모두 넣고 파일은 마지막에 `file`로 */
async function uploadPhoto(image: Blob): Promise<MentorProfile> {
  const ticket = await unwrap(
    api.POST("/api/v1/me/mentor-profile/image/uploads", { body: { content_type: "image/webp" } }),
  );
  const form = new FormData();
  for (const [key, value] of Object.entries(ticket.fields)) form.append(key, value);
  form.append("file", image, "profile.webp");
  const res = await fetch(ticket.url, { method: "POST", body: form });
  if (!res.ok) throw new PhotoUploadError();
  return unwrap(
    api.POST("/api/v1/me/mentor-profile/image/uploads/{upload_id}/confirm", {
      params: { path: { upload_id: ticket.upload_id } },
    }),
  );
}

/**
 * [저장] (F56): 글 입력을 먼저 저장하고, 사진은 그다음에 올리거나 지운다.
 * 바뀐 것만 보낸다. 마지막 응답으로 캐시를 고친다
 */
export function useSaveMentorProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ body, photo }: { body: ProfileUpdate | null; photo: PhotoChange }) => {
      let profile: MentorProfile | null = null;
      if (body) profile = await unwrap(api.PATCH("/api/v1/me/mentor-profile", { body }));
      if (photo.kind === "replace") profile = await uploadPhoto(photo.image);
      if (photo.kind === "remove") profile = await unwrap(api.DELETE("/api/v1/me/mentor-profile/image"));
      return profile;
    },
    onSettled: (profile) => {
      if (profile) queryClient.setQueryData(mentorProfileKeys.profile, profile);
      else void queryClient.invalidateQueries({ queryKey: mentorProfileKeys.profile });
    },
  });
}
