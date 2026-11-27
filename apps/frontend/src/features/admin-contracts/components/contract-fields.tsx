import { useInfiniteQuery } from "@tanstack/react-query";
import { CalendarRange, Layers, Search, UserRound, Wallet } from "lucide-react";
import { useId, useState, type InputHTMLAttributes } from "react";
import { Controller, useWatch, type UseFormReturn } from "react-hook-form";

import { PanelRow, PanelSection } from "@/components/panel";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { mentorsQuery } from "@/features/admin-mentors/api";
import { maskPhone } from "@/features/profile/mask";
import type { StaffCohort } from "@/features/staff/api";
import { pickableCohorts } from "@/features/staff/current-cohort";
import { useDebounced } from "@/lib/use-debounced";
import { cn } from "@/lib/utils";

import type { ContractType, PriceUnit, SettlementType, TimeBasis, VatType } from "../api";
import { moneyText, type ContractKey, type ContractValues } from "../contract-values";
import {
  isVendor,
  NEW_MENTOR_HELP,
  PRICE_UNIT_LABELS,
  SETTLEMENT_LABELS,
  TIME_BASIS_LABELS,
  TYPE_LABELS,
  TYPES,
} from "../labels";

type Form = UseFormReturn<ContractValues>;

const COMMON = "__common__";

function ErrorText({ form, name }: { form: Form; name: ContractKey }) {
  const message = form.formState.errors[name]?.message;
  return message ? <p className="mt-1 text-caption font-normal text-destructive-text">{message}</p> : null;
}

/** '라벨 | 입력' 한 줄 */
function TextRow({
  form,
  name,
  label,
  help,
  props = {},
  money = false,
  suffix,
}: {
  form: Form;
  name: ContractKey;
  label: string;
  help?: string;
  props?: InputHTMLAttributes<HTMLInputElement>;
  money?: boolean;
  suffix?: string;
}) {
  const id = useId();
  const invalid = !!form.formState.errors[name];
  return (
    <PanelRow label={label} htmlFor={id} help={help} top={invalid}>
      <div className="flex items-center gap-2 font-normal">
        {money ? (
          <Controller
            control={form.control}
            name={name}
            render={({ field }) => (
              <Input
                id={id}
                inputMode="numeric"
                aria-invalid={invalid}
                className="w-44 text-right"
                {...props}
                value={field.value}
                onChange={(e) => field.onChange(moneyText(e.target.value))}
                onBlur={field.onBlur}
              />
            )}
          />
        ) : (
          <Input id={id} aria-invalid={invalid} className="font-normal" {...props} {...form.register(name)} />
        )}
        {suffix ? <span className="shrink-0 text-body text-muted-foreground">{suffix}</span> : null}
      </div>
      <ErrorText form={form} name={name} />
    </PanelRow>
  );
}

function bootcampsOf(cohorts: readonly StaffCohort[]) {
  const map = new Map<string, { id: string; name: string; cohorts: StaffCohort[] }>();
  for (const c of pickableCohorts(cohorts)) {
    const b = map.get(c.bootcamp_id) ?? { id: c.bootcamp_id, name: c.bootcamp_name, cohorts: [] };
    b.cohorts.push(c);
    map.set(c.bootcamp_id, b);
  }
  return [...map.values()];
}

/** 종류 · 과정 / 기수 · 계약 명칭 (위저드 1단계, 서명 전 수정) */
export function BasicsSection({
  form,
  cohorts,
  lockType = false,
}: {
  form: Form;
  cohorts: readonly StaffCohort[];
  /** 수정에서는 종류를 바꾸지 않는다 */
  lockType?: boolean;
}) {
  const [type, bootcampId] = useWatch({ control: form.control, name: ["contract_type", "bootcamp_id"] });
  const bootcamps = bootcampsOf(cohorts);
  const bootcamp = bootcamps.find((b) => b.id === bootcampId);
  const errors = form.formState.errors;
  return (
    <PanelSection title="종류 · 과정 / 기수" icon={Layers}>
      <PanelRow label="종류">
        {lockType ? (
          TYPE_LABELS[type]
        ) : (
          <Controller
            control={form.control}
            name="contract_type"
            render={({ field }) => (
              <Segmented
                label="종류"
                value={field.value}
                onChange={(v: ContractType) => {
                  field.onChange(v);
                  if (v === "MENTOR") form.setValue("settlement_type", "UNIT_PRICE");
                }}
                options={TYPES.map((t) => ({ value: t, label: TYPE_LABELS[t] }))}
              />
            )}
          />
        )}
      </PanelRow>
      <PanelRow label="과정" top={!!errors.bootcamp_id}>
        <Controller
          control={form.control}
          name="bootcamp_id"
          render={({ field }) => (
            <Select
              value={field.value || undefined}
              onValueChange={(v) => {
                field.onChange(v);
                form.setValue("cohort_id", "");
              }}
            >
              <SelectTrigger aria-label="과정" aria-invalid={!!errors.bootcamp_id} className="font-normal">
                <SelectValue placeholder="과정 고르기" />
              </SelectTrigger>
              <SelectContent>
                {bootcamps.map((b) => (
                  <SelectItem key={b.id} value={b.id}>
                    {b.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
        <ErrorText form={form} name="bootcamp_id" />
      </PanelRow>
      <PanelRow label="기수" help="기수 없이 과정 전체에 걸린 계약이면 '과정 공통'을 골라요.">
        <Controller
          control={form.control}
          name="cohort_id"
          render={({ field }) => (
            <Select
              value={field.value || COMMON}
              onValueChange={(v) => field.onChange(v === COMMON ? "" : v)}
              disabled={!bootcamp}
            >
              <SelectTrigger aria-label="기수" className="font-normal">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={COMMON}>과정 공통</SelectItem>
                {(bootcamp?.cohorts ?? []).map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.cohort_number}기
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
      </PanelRow>
      <TextRow
        form={form}
        name="title"
        label="계약 명칭"
        props={{ maxLength: 100, placeholder: "예: 12기 백엔드 멘토 계약" }}
      />
    </PanelSection>
  );
}

/** 기존 멘토 고르기 (검색) */
function MentorPicker({ form }: { form: Form }) {
  const [q, setQ] = useState("");
  const term = useDebounced(q.trim());
  const found = useInfiniteQuery(mentorsQuery({ q: term || undefined }));
  const mentors = found.data?.pages[0]?.items ?? [];
  const [mentorId, label] = useWatch({ control: form.control, name: ["mentor_id", "mentor_label"] });
  return (
    <div className="flex flex-col gap-2 font-normal">
      {mentorId ? <span className="text-body-strong text-foreground">{label}</span> : null}
      <div className="relative">
        <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          aria-label="멘토 검색"
          placeholder="이름·이메일·휴대폰·닉네임 검색"
          value={q}
          maxLength={50}
          onChange={(e) => setQ(e.target.value)}
          className="pl-9"
        />
      </div>
      {found.isPending ? (
        <Spinner />
      ) : mentors.length === 0 ? (
        <p className="text-body text-muted-foreground">찾는 멘토가 없어요. '새 사람'으로 추가해 주세요.</p>
      ) : (
        <ul
          role="listbox"
          aria-label="멘토 후보"
          className="max-h-56 divide-y divide-border overflow-y-auto rounded-md border border-border"
        >
          {mentors.map((m) => {
            const selected = m.id === mentorId;
            const name = m.display_name !== m.name ? `${m.name}(${m.display_name})` : m.name;
            const pick = () => {
              form.setValue("mentor_id", m.id, { shouldDirty: true, shouldValidate: true });
              form.setValue("mentor_label", name);
              form.setValue("contractor_name", m.name);
              form.setValue("contractor_phone", m.phone_number ?? "");
              form.setValue("contractor_email", m.email ?? "");
            };
            return (
              <li
                key={m.id}
                role="option"
                aria-selected={selected}
                tabIndex={0}
                onClick={pick}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    pick();
                  }
                }}
                className={cn(
                  "flex cursor-pointer items-center gap-2 px-3 py-2 outline-none hover:bg-accent focus-visible:bg-accent",
                  selected && "bg-accent",
                )}
              >
                <span className="text-body-strong text-foreground">{name}</span>
                <span className="min-w-0 flex-1 truncate text-caption text-muted-foreground">
                  {[m.email, maskPhone(m.phone_number)].filter(Boolean).join(" · ")}
                  {m.is_registered ? "" : " · 가입 전"}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/**
 * 이름 또는 업체명 (위저드 2단계·수정·변경 등록). 멘토는 기존 멘토 고르기 또는 새 사람(A104),
 * 업체(SW·장비·기타)는 사업자등록번호·담당자 이름. `amend`면 이름은 바꾸지 않는다(A111⑤).
 */
export function PartySection({
  form,
  mode,
  canPickMentor,
}: {
  form: Form;
  mode: "create" | "edit" | "amend";
  canPickMentor: boolean;
}) {
  const [type, choice] = useWatch({ control: form.control, name: ["contract_type", "mentor_choice"] });
  const vendor = isVendor(type);
  const picking = mode === "create" && type === "MENTOR" && canPickMentor && choice === "existing";
  return (
    <PanelSection title="이름 또는 업체명" icon={UserRound}>
      {mode === "create" && type === "MENTOR" && canPickMentor ? (
        <PanelRow label="멘토">
          <Controller
            control={form.control}
            name="mentor_choice"
            render={({ field }) => (
              <Segmented
                label="멘토"
                value={field.value}
                onChange={field.onChange}
                options={[
                  { value: "existing", label: "기존 멘토" },
                  { value: "new", label: "새 사람" },
                ]}
              />
            )}
          />
        </PanelRow>
      ) : null}
      {picking ? (
        <PanelRow label="고르기" top>
          <MentorPicker form={form} />
          <ErrorText form={form} name="mentor_id" />
        </PanelRow>
      ) : (
        <>
          {mode === "amend" ? (
            <PanelRow
              label={vendor ? "업체명" : "이름"}
              help="이름은 바꿀 수 없어요. 다른 사람이면 해지하고 새 계약을 만들어요."
            >
              {form.getValues("contractor_name")}
            </PanelRow>
          ) : (
            <TextRow
              form={form}
              name="contractor_name"
              label={vendor ? "업체명" : "이름"}
              help={mode === "create" && type === "MENTOR" ? NEW_MENTOR_HELP : undefined}
              props={{ maxLength: 50 }}
            />
          )}
          <TextRow
            form={form}
            name="contractor_phone"
            label={vendor ? "전화" : "휴대폰"}
            props={{ inputMode: "tel", placeholder: vendor ? "선택 · 02-000-0000" : "010-0000-0000" }}
          />
        </>
      )}
      {!picking ? (
        <TextRow
          form={form}
          name="contractor_email"
          label="이메일"
          props={{ type: "email", maxLength: 255, placeholder: "선택" }}
        />
      ) : null}
      {vendor ? (
        <>
          <TextRow
            form={form}
            name="business_registration_number"
            label="사업자번호"
            help="사업자등록번호 10자리 (선택)"
            props={{ inputMode: "numeric", placeholder: "선택 · 123-45-67890" }}
          />
          <TextRow
            form={form}
            name="contact_person_name"
            label="담당자"
            props={{ maxLength: 50, placeholder: "선택 · 업체 담당자 이름" }}
          />
        </>
      ) : null}
    </PanelSection>
  );
}

const SETTLEMENTS: SettlementType[] = ["FIXED", "UNIT_PRICE", "ACTUAL_COST"];
const UNITS: PriceUnit[] = ["HOURLY", "PER_SESSION", "DAILY", "MONTHLY", "PER_ITEM"];
const VATS: { value: VatType; label: string }[] = [
  { value: "INCLUDED", label: "포함" },
  { value: "EXCLUDED", label: "별도" },
  { value: "NOT_APPLICABLE", label: "해당 없음" },
];

/** 금액 (위저드 3단계): 정산 유형에 따라 필요한 칸만, 멘토는 시간당·회당 단가·노쇼·정산 시간 기준 (A109④⑩) */
export function AmountSection({ form }: { form: Form }) {
  const [type, settlement] = useWatch({ control: form.control, name: ["contract_type", "settlement_type"] });
  const mentor = type === "MENTOR";
  const effective = mentor ? "UNIT_PRICE" : settlement;
  return (
    <PanelSection title="금액" icon={Wallet}>
      <PanelRow label="정산 유형" help={mentor ? "멘토 계약은 시간당·회당 단가만 고를 수 있어요." : undefined}>
        {mentor ? (
          "단가"
        ) : (
          <Controller
            control={form.control}
            name="settlement_type"
            render={({ field }) => (
              <Segmented
                label="정산 유형"
                value={field.value}
                onChange={field.onChange}
                options={SETTLEMENTS.map((s) => ({ value: s, label: SETTLEMENT_LABELS[s] }))}
              />
            )}
          />
        )}
      </PanelRow>
      {effective === "UNIT_PRICE" ? (
        <>
          <PanelRow label="단가 기준">
            <Controller
              control={form.control}
              name="price_unit"
              render={({ field }) => (
                <Segmented
                  label="단가 기준"
                  value={mentor && field.value !== "PER_SESSION" ? "HOURLY" : field.value}
                  onChange={field.onChange}
                  options={(mentor ? UNITS.slice(0, 2) : UNITS).map((u) => ({ value: u, label: PRICE_UNIT_LABELS[u] }))}
                />
              )}
            />
          </PanelRow>
          <TextRow form={form} name="unit_price" label="단가" money suffix="원" props={{ placeholder: "50,000" }} />
        </>
      ) : null}
      {mentor ? (
        <>
          <TextRow
            form={form}
            name="no_show_pay_amount"
            label="노쇼 금액"
            money
            suffix="원 / 노쇼 1건"
            props={{ placeholder: "0" }}
          />
          <PanelRow label="정산 시간" help="시간당 단가일 때 몇 시간으로 계산할지예요. 회당이면 차이가 없어요.">
            <Controller
              control={form.control}
              name="mentoring_time_basis"
              render={({ field }) => (
                <Segmented
                  label="정산 시간 기준"
                  value={field.value}
                  onChange={(v: TimeBasis) => field.onChange(v)}
                  options={(["STUDENT_REQUEST", "ACTUAL_DURATION"] as const).map((b) => ({
                    value: b,
                    label: TIME_BASIS_LABELS[b],
                  }))}
                />
              )}
            />
          </PanelRow>
        </>
      ) : null}
      <TextRow
        form={form}
        name="total_amount"
        label={effective === "FIXED" ? "계약 금액" : effective === "ACTUAL_COST" ? "한도액" : "예상 총액"}
        help={effective === "FIXED" ? undefined : "선택"}
        money
        suffix="원"
      />
      <PanelRow label="부가세">
        <Controller
          control={form.control}
          name="vat_type"
          render={({ field }) => (
            <Segmented label="부가세" value={field.value} onChange={field.onChange} options={VATS} />
          )}
        />
      </PanelRow>
      <TextRow
        form={form}
        name="amount_note"
        label="금액 메모"
        props={{ maxLength: 200, placeholder: "선택 · 예: 매월 말일 지급" }}
      />
    </PanelSection>
  );
}

/** 기간 (각각 선택, A109③) */
export function PeriodSection({ form }: { form: Form }) {
  const id = useId();
  const errors = form.formState.errors;
  return (
    <PanelSection title="기간" icon={CalendarRange}>
      <PanelRow
        label="계약 기간"
        help="둘 다 선택이에요. 시작일이 오면 '이행 중'으로, 종료일이 지나면 '종료'로 바뀌어요."
        top={!!errors.end_date}
      >
        <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 font-normal">
          <Input id={id} type="date" aria-label="시작일" {...form.register("start_date")} />
          <span aria-hidden className="text-muted-foreground">
            ~
          </span>
          <Input type="date" aria-label="종료일" aria-invalid={!!errors.end_date} {...form.register("end_date")} />
        </div>
        <ErrorText form={form} name="end_date" />
      </PanelRow>
    </PanelSection>
  );
}
