import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";

import type { MentorProfile, PhotoChange } from "./api";
import { displayNameOf, formOf, mentorProfileSchema, type MentorProfileForm } from "./form";
import { photoProblem, toProfilePhoto } from "./image";

/**
 * 멘토 프로필 편집 상태 (F56·F79): 멘토 '내 프로필'과 운영진 대리 수정이 함께 쓴다.
 * 사진은 브라우저가 줄여 두었다가 [저장] 때 함께 올린다. 입력은 `components/profile-fields.tsx`
 */
const SAVE_ERRORS: Record<string, string> = {
  nickname_required: "닉네임으로 보이려면 닉네임을 적어 주세요.",
  invalid_nickname: "닉네임을 확인해 주세요.",
  invalid_headline: "한 줄 소개를 확인해 주세요.",
  invalid_expertise: "전문 분야를 확인해 주세요.",
  invalid_introduction: "소개를 확인해 주세요.",
  invalid_image: "사진을 올리지 못했어요. 다른 사진으로 다시 시도해 주세요.",
};

export function saveErrorText(e: unknown): string {
  const code = e instanceof ApiError ? e.code : undefined;
  return (code && SAVE_ERRORS[code]) ?? "저장하지 못했어요. 잠시 후 다시 시도해 주세요.";
}

type Photo = PhotoChange & { preview?: string };

export function useProfileEditor(profile: MentorProfile) {
  const form = useForm<MentorProfileForm>({ resolver: zodResolver(mentorProfileSchema), values: formOf(profile) });
  const [photo, setPhoto] = useState<Photo>({ kind: "keep" });
  const [processing, setProcessing] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const values = useWatch({ control: form.control }) as MentorProfileForm;
  const dirty = form.formState.isDirty || photo.kind !== "keep";

  // 미리 보기 주소는 바꾸거나 떠날 때 놓아 준다
  useEffect(() => () => (photo.preview ? URL.revokeObjectURL(photo.preview) : undefined), [photo.preview]);

  const shownPhoto =
    photo.kind === "replace" ? (photo.preview ?? null) : photo.kind === "remove" ? null : profile.profile_image_url;
  const displayName = displayNameOf(profile.name, values);

  const onPick = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const problem = photoProblem(file);
    if (problem) {
      toast.error(problem);
      return;
    }
    setProcessing(true);
    try {
      const image = await toProfilePhoto(file);
      setPhoto({ kind: "replace", image, preview: URL.createObjectURL(image) });
    } catch {
      toast.error("사진을 읽지 못했어요. 다른 사진을 골라 주세요.");
    } finally {
      setProcessing(false);
    }
  };

  const onRemovePhoto = () => setPhoto(profile.profile_image_url ? { kind: "remove" } : { kind: "keep" });

  const resetPhoto = () => setPhoto({ kind: "keep" });
  /** 저장 전 내용을 버린다 (운영진 수정 [취소]) */
  const discard = () => {
    form.reset(formOf(profile));
    resetPhoto();
  };

  return {
    form,
    values,
    photo,
    processing,
    fileRef,
    dirty,
    shownPhoto,
    displayName,
    onPick,
    onRemovePhoto,
    resetPhoto,
    discard,
  };
}

export type ProfileEditor = ReturnType<typeof useProfileEditor>;
