import { z } from "zod";

import type {
  AmendmentChanges,
  Contract,
  ContractFields,
  ContractType,
  ContractUpdate,
  PriceUnit,
  SettlementType,
  TimeBasis,
  VatType,
} from "./api";
import { isVendor } from "./labels";

const MOBILE = /^01[0-9]\d{7,8}$/;
const PHONE = /^0\d{8,10}$/;
const MAX_AMOUNT = 2_000_000_000;

export const digits = (v: string) => v.replace(/\D/g, "");
/** 금액 입력 표시: 숫자만 남기고 세 자리마다 쉼표 */
export const moneyText = (v: string) => {
  const d = digits(v).replace(/^0+(?=\d)/, "");
  return d ? Number(d).toLocaleString("ko-KR") : "";
};
const money = (v: string): number | null => (digits(v) ? Number(digits(v)) : null);

/** 계약 입력값 (위저드·수정·변경 등록 공통). 금액은 쉼표가 들어간 글자, 기수 ""는 과정 공통 */
export const contractSchema = z
  .object({
    contract_type: z.enum(["MENTOR", "INSTRUCTOR", "SW", "EQUIPMENT", "OTHER"]),
    bootcamp_id: z.string(),
    cohort_id: z.string(),
    title: z.string().trim().max(100, "100자까지 적을 수 있어요"),
    mentor_choice: z.enum(["existing", "new"]),
    mentor_id: z.string(),
    mentor_label: z.string(),
    contractor_name: z.string().trim().max(50, "50자까지 적을 수 있어요"),
    contractor_phone: z.string().trim(),
    contractor_email: z.string().trim().max(255),
    business_registration_number: z.string().trim(),
    contact_person_name: z.string().trim().max(50, "50자까지 적을 수 있어요"),
    settlement_type: z.enum(["FIXED", "UNIT_PRICE", "ACTUAL_COST"]),
    total_amount: z.string(),
    unit_price: z.string(),
    price_unit: z.enum(["HOURLY", "PER_SESSION", "DAILY", "MONTHLY", "PER_ITEM"]),
    vat_type: z.enum(["INCLUDED", "EXCLUDED", "NOT_APPLICABLE"]),
    amount_note: z.string().trim().max(200, "200자까지 적을 수 있어요"),
    no_show_pay_amount: z.string(),
    mentoring_time_basis: z.enum(["STUDENT_REQUEST", "ACTUAL_DURATION"]),
    start_date: z.string(),
    end_date: z.string(),
  })
  .superRefine((v, ctx) => {
    const fail = (path: string, message: string) => ctx.addIssue({ code: "custom", path: [path], message });
    if (!v.bootcamp_id) fail("bootcamp_id", "과정을 골라 주세요");
    if (!v.title.trim()) fail("title", "계약 명칭을 적어 주세요");
    // 이름 또는 업체명 (A109⑤)
    const mentor = v.contract_type === "MENTOR";
    if (mentor && v.mentor_choice === "existing") {
      if (!v.mentor_id) fail("mentor_id", "멘토를 골라 주세요");
    } else {
      if (!v.contractor_name.trim())
        fail("contractor_name", isVendor(v.contract_type) ? "업체명을 적어 주세요" : "이름을 적어 주세요");
      const phone = digits(v.contractor_phone);
      if (!isVendor(v.contract_type)) {
        if (!MOBILE.test(phone)) fail("contractor_phone", "휴대폰 번호를 확인해 주세요");
      } else if (phone && !PHONE.test(phone)) fail("contractor_phone", "전화번호를 확인해 주세요");
    }
    if (v.contractor_email && !z.email().safeParse(v.contractor_email).success)
      fail("contractor_email", "이메일을 확인해 주세요");
    if (v.business_registration_number && digits(v.business_registration_number).length !== 10)
      fail("business_registration_number", "사업자등록번호는 숫자 10자리예요");
    // 금액 (A109④⑩)
    const over = (key: "total_amount" | "unit_price" | "no_show_pay_amount") => {
      const n = money(v[key]);
      if (n !== null && n > MAX_AMOUNT) fail(key, "금액이 너무 커요");
    };
    over("total_amount");
    over("unit_price");
    over("no_show_pay_amount");
    if (mentor) {
      if (money(v.unit_price) === null) fail("unit_price", "단가를 적어 주세요");
      if (money(v.no_show_pay_amount) === null) fail("no_show_pay_amount", "노쇼 금액을 적어 주세요(없으면 0)");
    } else if (v.settlement_type === "FIXED") {
      if (money(v.total_amount) === null) fail("total_amount", "계약 금액을 적어 주세요");
    } else if (v.settlement_type === "UNIT_PRICE") {
      if (money(v.unit_price) === null) fail("unit_price", "단가를 적어 주세요");
    }
    if (v.start_date && v.end_date && v.end_date < v.start_date)
      fail("end_date", "종료일은 시작일과 같거나 뒤여야 해요");
  });
export type ContractValues = z.infer<typeof contractSchema>;
export type ContractKey = keyof ContractValues;

/** 위저드 단계별로 검사할 항목 */
export const STEP_FIELDS: Record<number, ContractKey[]> = {
  0: ["contract_type", "bootcamp_id", "cohort_id", "title"],
  1: [
    "mentor_id",
    "contractor_name",
    "contractor_phone",
    "contractor_email",
    "business_registration_number",
    "contact_person_name",
  ],
  2: [
    "settlement_type",
    "total_amount",
    "unit_price",
    "price_unit",
    "vat_type",
    "amount_note",
    "no_show_pay_amount",
    "start_date",
    "end_date",
  ],
};

export function emptyValues(scope: { bootcampId?: string; cohortId?: string }): ContractValues {
  return {
    contract_type: "MENTOR",
    bootcamp_id: scope.bootcampId ?? "",
    cohort_id: scope.cohortId ?? "",
    title: "",
    mentor_choice: "existing",
    mentor_id: "",
    mentor_label: "",
    contractor_name: "",
    contractor_phone: "",
    contractor_email: "",
    business_registration_number: "",
    contact_person_name: "",
    settlement_type: "UNIT_PRICE",
    total_amount: "",
    unit_price: "",
    price_unit: "HOURLY",
    vat_type: "NOT_APPLICABLE",
    amount_note: "",
    no_show_pay_amount: "0",
    mentoring_time_basis: "ACTUAL_DURATION",
    start_date: "",
    end_date: "",
  };
}

const moneyOf = (n: number | null) => (n === null ? "" : n.toLocaleString("ko-KR"));

export function valuesOf(c: Contract): ContractValues {
  return {
    contract_type: c.contract_type,
    bootcamp_id: c.bootcamp_id,
    cohort_id: c.cohort_id ?? "",
    title: c.title,
    // 새 사람의 멘토 계약은 계약 완료 전까지 멘토가 없다 (A115)
    mentor_choice: c.mentor_id ? "existing" : "new",
    mentor_id: c.mentor_id ?? "",
    mentor_label: "",
    contractor_name: c.contractor_name,
    contractor_phone: c.contractor_phone ?? "",
    contractor_email: c.contractor_email ?? "",
    business_registration_number: c.business_registration_number ?? "",
    contact_person_name: c.contact_person_name ?? "",
    settlement_type: c.settlement_type,
    total_amount: moneyOf(c.total_amount),
    unit_price: moneyOf(c.unit_price),
    price_unit: c.price_unit ?? "HOURLY",
    vat_type: c.vat_type,
    amount_note: c.amount_note ?? "",
    no_show_pay_amount: moneyOf(c.no_show_pay_amount),
    mentoring_time_basis: c.mentoring_time_basis ?? "ACTUAL_DURATION",
    start_date: c.start_date ?? "",
    end_date: c.end_date ?? "",
  };
}

const orNull = (v: string) => (v.trim() ? v.trim() : null);

/** 종류에 맞는 칸만 남긴 내용 (계약 명칭·당사자 연락처·금액·기간) */
function terms(v: ContractValues) {
  const mentor = v.contract_type === "MENTOR";
  const vendor = isVendor(v.contract_type);
  const settlement: SettlementType = mentor ? "UNIT_PRICE" : v.settlement_type;
  const unit = settlement === "UNIT_PRICE";
  const price: PriceUnit | null = unit ? (mentor && v.price_unit !== "PER_SESSION" ? "HOURLY" : v.price_unit) : null;
  return {
    title: v.title.trim(),
    contractor_phone: orNull(digits(v.contractor_phone)),
    contractor_email: orNull(v.contractor_email),
    business_registration_number: vendor ? orNull(digits(v.business_registration_number)) : null,
    contact_person_name: vendor ? orNull(v.contact_person_name) : null,
    start_date: v.start_date || null,
    end_date: v.end_date || null,
    settlement_type: settlement,
    total_amount: money(v.total_amount),
    unit_price: unit ? money(v.unit_price) : null,
    price_unit: price,
    vat_type: v.vat_type as VatType,
    amount_note: orNull(v.amount_note),
    no_show_pay_amount: mentor ? money(v.no_show_pay_amount) : null,
    mentoring_time_basis: mentor ? (v.mentoring_time_basis as TimeBasis) : null,
  };
}

/** 계약 추가 본문 */
export function fieldsOf(
  v: ContractValues,
  extra: { manager_employee_id: string; contract_file_id: string | null },
): ContractFields {
  const existing = v.contract_type === "MENTOR" && v.mentor_choice === "existing";
  return {
    ...terms(v),
    contract_type: v.contract_type as ContractType,
    bootcamp_id: v.bootcamp_id,
    cohort_id: v.cohort_id || null,
    contractor_name: v.contractor_name.trim(),
    mentor_id: existing ? v.mentor_id : null,
    ...extra,
  };
}

/** 서명 전 수정 (A109⑨): 바뀐 항목만 */
export function updateOf(before: Contract, v: ContractValues): ContractUpdate {
  const next = {
    ...terms(v),
    bootcamp_id: v.bootcamp_id,
    cohort_id: v.cohort_id || null,
    contractor_name: v.contractor_name.trim(),
  };
  return changed(before, next) as ContractUpdate;
}

/** 서명 후 변경 계약 (A109⑨·A111⑤): 바꿀 수 있는 항목 중 바뀐 것만 */
export function amendmentOf(before: Contract, v: ContractValues): AmendmentChanges {
  return changed(before, terms(v)) as AmendmentChanges;
}

function changed(before: Contract, next: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(next)) {
    const old = (before as unknown as Record<string, unknown>)[key] ?? null;
    if ((value ?? null) !== old) out[key] = value;
  }
  return out;
}
