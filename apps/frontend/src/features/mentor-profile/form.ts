import { z } from "zod";

import { expertiseChips } from "@/features/apply/api";

import type { MentorProfile, ProfileUpdate } from "./api";

export const NICKNAME_MAX_LENGTH = 30;
export const HEADLINE_MAX_LENGTH = 100;
export const EXPERTISE_MAX_LENGTH = 200;
export const INTRODUCTION_MAX_LENGTH = 10_000;

/** 전문 분야는 쉼표로 이어 저장한다 (F30·F56) */
export const EXPERTISE_SEPARATOR = ", ";

export function joinExpertise(items: readonly string[]): string {
  return items.join(EXPERTISE_SEPARATOR);
}

export const mentorProfileSchema = z
  .object({
    nickname: z.string().trim().max(NICKNAME_MAX_LENGTH, `닉네임은 ${NICKNAME_MAX_LENGTH}자까지 적을 수 있어요.`),
    preference: z.enum(["NAME", "NICKNAME"]),
    headline: z.string().trim().max(HEADLINE_MAX_LENGTH, `한 줄 소개는 ${HEADLINE_MAX_LENGTH}자까지 적을 수 있어요.`),
    expertise: z.array(z.string()).refine((items) => joinExpertise(items).length <= EXPERTISE_MAX_LENGTH, {
      message: `전문 분야는 모두 합쳐 ${EXPERTISE_MAX_LENGTH}자까지 적을 수 있어요.`,
    }),
    introduction: z
      .string()
      .max(INTRODUCTION_MAX_LENGTH, `소개는 ${INTRODUCTION_MAX_LENGTH.toLocaleString("ko-KR")}자까지 적을 수 있어요.`),
  })
  .superRefine((v, ctx) => {
    if (v.preference === "NICKNAME" && !v.nickname.trim())
      ctx.addIssue({ code: "custom", path: ["nickname"], message: "닉네임으로 보이려면 닉네임을 적어 주세요." });
  });

export type MentorProfileForm = z.infer<typeof mentorProfileSchema>;

export function formOf(profile: MentorProfile): MentorProfileForm {
  return {
    nickname: profile.nickname ?? "",
    preference: profile.display_name_preference,
    headline: profile.headline ?? "",
    expertise: expertiseChips(profile.expertise),
    introduction: profile.introduction ?? "",
  };
}

function text(value: string): string | null {
  return value.trim() || null;
}

/** 입력값 → PATCH 본문. 빈 값은 null로 지운다 */
export function bodyOf(v: MentorProfileForm): ProfileUpdate {
  return {
    nickname: text(v.nickname),
    display_name_preference: v.preference,
    headline: text(v.headline),
    expertise: v.expertise.length ? joinExpertise(v.expertise) : null,
    introduction: text(v.introduction),
  };
}

/** 보일 이름 (A22): 닉네임을 골랐고 닉네임이 있으면 닉네임, 아니면 실명 */
export function displayNameOf(name: string, v: Pick<MentorProfileForm, "nickname" | "preference">): string {
  return v.preference === "NICKNAME" && v.nickname.trim() ? v.nickname.trim() : name;
}

/** 칩 하나 추가: 쉼표는 구분자라 빼고, 빈 값·중복은 넣지 않는다 */
export function addChip(items: readonly string[], raw: string): string[] {
  const chips = raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const next = [...items];
  for (const c of chips) if (!next.includes(c)) next.push(c);
  return next;
}
