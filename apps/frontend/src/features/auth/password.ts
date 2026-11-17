import { z } from "zod";

/** 비밀번호 규칙 (decisions A30: 8~64자, 영문·숫자·특수문자 각각 1개 이상). 백엔드 `credentials.py`와 같은 판정. */
export const PASSWORD_RULES = [
  { id: "length", label: "8~64자", test: (v: string) => v.length >= 8 && v.length <= 64 },
  { id: "letter", label: "영문 포함", test: (v: string) => /[A-Za-z]/.test(v) },
  { id: "digit", label: "숫자 포함", test: (v: string) => /\d/.test(v) },
  { id: "special", label: "특수문자 포함", test: (v: string) => /[^\p{L}\p{N}\s]/u.test(v) },
] as const;

export const passwordSchema = z
  .string()
  .refine((v) => PASSWORD_RULES.every((rule) => rule.test(v)), "비밀번호 규칙을 모두 지켜 주세요.");

export const emailSchema = z.string().trim().min(1, "이메일을 입력해 주세요.").email("이메일 형식이 올바르지 않아요.");
