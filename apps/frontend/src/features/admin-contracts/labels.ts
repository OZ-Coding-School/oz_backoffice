import type { BadgeProps } from "@/components/ui/badge";
import { ApiError } from "@/api/errors";

import type { Contract, ContractStatus, EducatorType } from "./api";

export const STATUS: Record<ContractStatus, { label: string; badge: NonNullable<BadgeProps["variant"]> }> = {
  DRAFT: { label: "작성 중", badge: "outline" },
  ACTIVE: { label: "진행 중", badge: "success" },
  ENDED: { label: "종료", badge: "secondary" },
  TERMINATED: { label: "해지", badge: "destructive" },
};

export const TYPE_LABELS: Record<EducatorType, string> = { MENTOR: "멘토", INSTRUCTOR: "강사" };

const dot = (date: string) => date.replaceAll("-", ".");

/** "2026.11.01 ~ 2027.04.30" */
export const period = (c: Pick<Contract, "start_date" | "end_date">) => `${dot(c.start_date)} ~ ${dot(c.end_date)}`;

/** 연결: 멘토 이름(닉네임) · 가입 전 · 미연결 */
export function linkedText(c: Contract): { text: string; muted: boolean } {
  const p = c.linked_profile;
  if (!p) return { text: "미연결", muted: true };
  const name = p.display_name && p.display_name !== p.name ? `${p.name}(${p.display_name})` : p.name;
  return { text: name, muted: false };
}

/** 파일 크기: "182KB" · "1.2MB" */
export function fileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
  return `${Math.max(1, Math.round(bytes / 1024))}KB`;
}

const ERRORS: Record<string, string> = {
  ambiguous_mentor: "이름과 휴대폰이 같은 멘토가 여럿이에요. 멘토를 확인해 주세요.",
  contract_file_required: "계약서를 올린 뒤 확정할 수 있어요.",
  contract_not_deletable: "작성 중인 계약만 지울 수 있어요.",
  contract_not_editable: "확정한 계약은 담당 직원만 바꿀 수 있어요.",
  invalid_contract_period: "기간을 확인해 주세요. 종료일은 시작일보다 뒤여야 해요.",
  invalid_contract_title: "제목을 확인해 주세요.",
  invalid_email: "이메일을 확인해 주세요.",
  invalid_contract_transition: "지금 상태에서는 할 수 없어요.",
  employee_not_found: "담당 직원을 찾을 수 없어요.",
  unsupported_file_type: "PDF 파일만 올릴 수 있어요.",
  invalid_contract_file: "PDF가 아니거나 10MB를 넘었어요.",
  file_name_too_long: "파일 이름이 너무 길어요(100자까지).",
  invalid_file_name: "파일 이름을 확인해 주세요.",
  mentor_not_found: "멘토를 찾을 수 없어요.",
  contract_type_mismatch: "계약 유형과 맞지 않아요.",
};

export function contractError(e: unknown): string {
  const code = e instanceof ApiError ? e.code : undefined;
  return (code && ERRORS[code]) ?? "처리하지 못했어요. 잠시 후 다시 시도해 주세요.";
}
