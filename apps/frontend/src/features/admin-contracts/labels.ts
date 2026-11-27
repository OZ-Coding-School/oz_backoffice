import type { BadgeProps } from "@/components/ui/badge";
import { ApiError } from "@/api/errors";

import type {
  Contract,
  ContractStatus,
  ContractType,
  PriceUnit,
  SettlementType,
  TerminationReason,
  TimeBasis,
  VatType,
} from "./api";

export const STATUS: Record<ContractStatus, { label: string; badge: NonNullable<BadgeProps["variant"]> }> = {
  DRAFT: { label: "초안", badge: "outline" },
  IN_PROGRESS: { label: "진행 중", badge: "warning" },
  SIGNED: { label: "계약 완료", badge: "info" },
  ACTIVE: { label: "이행 중", badge: "success" },
  ENDED: { label: "종료", badge: "secondary" },
  CANCELED: { label: "취소", badge: "dashed" },
  TERMINATED: { label: "해지", badge: "destructive" },
};

/** 상태 단계 표시 (F96): 초안 → 진행 중 → 계약 완료 → 이행 중 → 종료 */
export const FLOW: readonly ContractStatus[] = ["DRAFT", "IN_PROGRESS", "SIGNED", "ACTIVE", "ENDED"];

export const TYPE_LABELS: Record<ContractType, string> = {
  MENTOR: "멘토",
  INSTRUCTOR: "강사",
  SW: "SW",
  EQUIPMENT: "장비",
  OTHER: "기타",
};
export const TYPES: readonly ContractType[] = ["MENTOR", "INSTRUCTOR", "SW", "EQUIPMENT", "OTHER"];

/** 업체 계약 (A109⑤): 이름 대신 업체명, 사업자등록번호·담당자 */
export const isVendor = (t: ContractType) => t === "SW" || t === "EQUIPMENT" || t === "OTHER";

export const SETTLEMENT_LABELS: Record<SettlementType, string> = {
  FIXED: "정액",
  UNIT_PRICE: "단가",
  ACTUAL_COST: "실비",
};
export const PRICE_UNIT_LABELS: Record<PriceUnit, string> = {
  HOURLY: "시간당",
  PER_SESSION: "회당",
  DAILY: "일당",
  MONTHLY: "월",
  PER_ITEM: "건당",
};
export const VAT_LABELS: Record<VatType, string> = {
  INCLUDED: "부가세 포함",
  EXCLUDED: "부가세 별도",
  NOT_APPLICABLE: "부가세 해당 없음",
};
export const TIME_BASIS_LABELS: Record<TimeBasis, string> = {
  STUDENT_REQUEST: "신청 시간",
  ACTUAL_DURATION: "실제 진행 시간",
};
export const TERMINATION_LABELS: Record<TerminationReason, string> = {
  TERMINATED_BY_FAULT: "귀책 사유로 인한 해지",
  TERMINATED_BY_MUTUAL_AGREEMENT: "합의에 의한 해지",
  TERMINATED_BY_UNILATERAL: "일방적 해지",
};

const dot = (date: string | null | undefined) => (date ? date.replaceAll("-", ".") : "");
export const dotDate = (date: string | null | undefined) => dot(date) || "—";

/** "2026.11.01 ~ 2027.04.30" · "2026.11.01 ~" · "기간 미정" */
export function period(c: Pick<Contract, "start_date" | "end_date">): string {
  if (!c.start_date && !c.end_date) return "기간 미정";
  return `${dot(c.start_date)} ~ ${dot(c.end_date)}`.trim();
}

/** 과정 / 기수 (F96): "백엔드 부트캠프 / 12기" · "백엔드 부트캠프 / 공통" */
export function academyText(c: Pick<Contract, "bootcamp_name" | "cohort_number">): string {
  const cohort = c.cohort_number ? `${c.cohort_number}기` : "공통";
  return c.bootcamp_name ? `${c.bootcamp_name} / ${cohort}` : cohort;
}

/** 두 날짜("YYYY-MM-DD") 사이 일수 (to − from). 달력 날짜라 시간대와 무관하다 */
function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000);
}

/** 기간 보조 문구: "시작까지 12일" · "종료까지 45일" · "오늘 종료". 끝난 계약·날짜 없음은 null */
export function periodHint(
  c: Pick<Contract, "status" | "start_date" | "end_date">,
  today: string,
): { text: string; soon: boolean } | null {
  if (c.status === "SIGNED" && c.start_date && c.start_date > today) {
    const d = daysBetween(today, c.start_date);
    return { text: `시작까지 ${d}일`, soon: d <= 7 };
  }
  if ((c.status === "ACTIVE" || c.status === "SIGNED") && c.end_date && c.end_date >= today) {
    const d = daysBetween(today, c.end_date);
    return { text: d === 0 ? "오늘 종료" : `종료까지 ${d}일`, soon: d <= 30 };
  }
  return null;
}

export const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;

/** 금액 한 줄 (F96): "시간당 50,000원" · "정액 1,200,000원" · "실비 한도 2,000,000원" */
export function amountText(
  c: Pick<Contract, "settlement_type" | "total_amount" | "unit_price" | "price_unit">,
): string {
  if (c.settlement_type === "UNIT_PRICE" && c.unit_price != null && c.price_unit)
    return `${PRICE_UNIT_LABELS[c.price_unit]} ${won(c.unit_price)}`;
  if (c.settlement_type === "FIXED") return c.total_amount != null ? `정액 ${won(c.total_amount)}` : "정액";
  if (c.settlement_type === "ACTUAL_COST") return c.total_amount != null ? `실비 한도 ${won(c.total_amount)}` : "실비";
  return SETTLEMENT_LABELS[c.settlement_type];
}

/** 금액 아랫줄: 멘토는 노쇼, 그 밖은 부가세 */
export function amountSub(c: Pick<Contract, "contract_type" | "no_show_pay_amount" | "vat_type">): string {
  if (c.contract_type === "MENTOR" && c.no_show_pay_amount != null) return `노쇼 ${won(c.no_show_pay_amount)}`;
  return VAT_LABELS[c.vat_type];
}

/** 연결: 멘토 이름(닉네임) · 가입 전 · 미연결 */
export function linkedText(c: Contract): { text: string; muted: boolean } {
  const p = c.linked_profile;
  // 새 사람의 멘토 계약은 계약 완료 때 멘토가 정해진다 (A115)
  if (!p && c.contract_type === "MENTOR" && ["DRAFT", "IN_PROGRESS"].includes(c.status))
    return { text: "계약 완료 때 연결", muted: true };
  if (!p) return { text: "미연결", muted: true };
  const name = p.display_name && p.display_name !== p.name ? `${p.name}(${p.display_name})` : p.name;
  return { text: name, muted: false };
}

/** 파일 크기: "182KB" · "1.2MB" */
export function fileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
  return `${Math.max(1, Math.round(bytes / 1024))}KB`;
}

/** 변경 이력의 항목 이름 */
export const FIELD_LABELS: Record<string, string> = {
  title: "계약 명칭",
  contractor_phone: "전화",
  contractor_email: "이메일",
  business_registration_number: "사업자등록번호",
  contact_person_name: "담당자 이름",
  start_date: "시작일",
  end_date: "종료일",
  settlement_type: "정산 유형",
  total_amount: "계약 금액",
  unit_price: "단가",
  price_unit: "단가 기준",
  vat_type: "부가세",
  amount_note: "금액 메모",
  no_show_pay_amount: "노쇼 금액",
  mentoring_time_basis: "정산 시간 기준",
};

/** 변경 이력 값 한 칸을 읽기 좋게 */
export function fieldValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "없음";
  if (typeof value === "number") return key === "unit_price" || key.endsWith("amount") ? won(value) : String(value);
  const text = String(value);
  if (key === "settlement_type") return SETTLEMENT_LABELS[text as SettlementType] ?? text;
  if (key === "price_unit") return PRICE_UNIT_LABELS[text as PriceUnit] ?? text;
  if (key === "vat_type") return VAT_LABELS[text as VatType] ?? text;
  if (key === "mentoring_time_basis") return TIME_BASIS_LABELS[text as TimeBasis] ?? text;
  if (key.endsWith("_date")) return dotDate(text);
  return text;
}

const ERRORS: Record<string, string> = {
  ambiguous_mentor:
    "이름과 휴대폰이 같은 멘토가 여럿이라 계약 완료를 할 수 없어요. 이 계약을 취소하고 기존 멘토를 골라 다시 만들어 주세요.",
  contract_file_required: "계약서 원본을 올린 뒤 진행할 수 있어요.",
  signed_contract_file_required: "서명된 계약서를 올려 주세요.",
  mentor_contract_move_forbidden: "멘토 계약은 다른 멘토로 옮길 수 없어요.",
  signed_contract_file_same: "서명된 계약서는 원본과 다른 파일이어야 해요.",
  contract_not_deletable: "초안인 계약만 지울 수 있어요.",
  contract_not_editable: "서명한 계약은 변경 등록으로 바꿔요.",
  contract_field_not_amendable: "변경 계약으로 바꿀 수 없는 항목이에요.",
  amendment_no_changes: "바뀐 항목이 없어요.",
  invalid_amendment_reason: "변경 사유를 확인해 주세요(500자까지).",
  invalid_cancel_reason: "취소 사유를 확인해 주세요(500자까지).",
  invalid_contract_period: "기간을 확인해 주세요. 종료일은 시작일보다 뒤여야 해요.",
  invalid_contract_title: "계약 명칭을 확인해 주세요.",
  invalid_contract_amount: "금액을 확인해 주세요.",
  invalid_mentor_contract_terms: "멘토 계약은 시간당·회당 단가와 노쇼 금액, 정산 시간 기준이 필요해요.",
  invalid_contract_party: "이름 또는 업체명과 연락처를 확인해 주세요.",
  invalid_business_registration_number: "사업자등록번호는 숫자 10자리예요.",
  invalid_email: "이메일을 확인해 주세요.",
  invalid_contract_transition: "지금 상태에서는 할 수 없어요.",
  contract_has_end_date: "종료일이 있는 계약은 종료일이 지나면 자동으로 끝나요.",
  bootcamp_not_found: "과정을 찾을 수 없어요.",
  cohort_not_found: "기수를 찾을 수 없어요.",
  cohort_not_in_bootcamp: "그 과정의 기수가 아니에요.",
  employee_not_found: "담당 직원을 찾을 수 없어요.",
  unsupported_file_type: "PDF 파일만 올릴 수 있어요.",
  invalid_contract_file: "PDF가 아니거나 10MB를 넘었어요.",
  file_name_too_long: "파일 이름이 너무 길어요(100자까지).",
  invalid_file_name: "파일 이름을 확인해 주세요.",
  mentor_not_found: "멘토를 찾을 수 없어요.",
  contract_type_mismatch: "계약 종류와 맞지 않아요.",
  contract_file_in_use: "다른 계약에 붙은 계약서예요.",
};

export function contractError(e: unknown): string {
  const code = e instanceof ApiError ? e.code : undefined;
  if (code === "permission_denied" || (e instanceof ApiError && e.status === 403))
    return "이 계약을 관리할 권한이 없어요.";
  return (code && ERRORS[code]) ?? "처리하지 못했어요. 잠시 후 다시 시도해 주세요.";
}

export const FILE_HELP =
  "상대방에게 보낼 서명 전 계약서예요. PDF 10MB까지, 진행을 시작하려면 있어야 해요. 서명된 계약서는 [계약 완료]에서 올려요.";
export const MENTOR_HELP =
  "멘토 계약은 만들 때 정한 멘토에 속하고 바꿀 수 없어요. 잘못 만들었으면 초안은 삭제, 진행 중이면 취소한 뒤 새로 만들어요.";
export const NEW_MENTOR_HELP =
  "멘토는 계약 완료 때 정해져요. 이름·휴대폰이 같은 멘토가 있으면 그 멘토에 붙고, 없으면 가입 전 멘토가 생겨요.";
