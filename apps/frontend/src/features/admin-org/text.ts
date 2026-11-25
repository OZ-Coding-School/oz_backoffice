import { ApiError } from "@/api/errors";

export function errorText(e: unknown): string {
  return e instanceof ApiError ? e.message : "저장하지 못했어요. 잠시 후 다시 시도해 주세요.";
}

/** 목적격 조사: 받침이 있으면 '을', 없으면 '를' (한글이 아니면 '을(를)') */
export function eul(word: string): string {
  const last = word.trim().at(-1) ?? "";
  const code = last.charCodeAt(0) - 0xac00;
  if (code < 0 || code > 11171) return `${word}을(를)`;
  return `${word}${code % 28 ? "을" : "를"}`;
}
