import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { Check, ClipboardCheck, FileText, UserRound } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";

import { PanelHead, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DiscardDialog } from "@/features/admin-org/components/shared";
import { maskPhone } from "@/features/profile/mask";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { cn } from "@/lib/utils";

import { managerCandidatesQuery, useCreateContract, type Contract, type ContractFile } from "../api";
import { contractSchema, emptyValues, fieldsOf, STEP_FIELDS, type ContractValues } from "../contract-values";
import { amountSub, amountText, contractError, FILE_HELP, isVendor, period } from "../labels";
import { AmountSection, BasicsSection, PartySection, PeriodSection } from "./contract-fields";
import { FilePicker } from "./file-picker";
import { ManagerList, type ManagerChoice } from "./pickers";
import { ContractTypeBadge } from "./type-badge";

const STEPS = ["종류·과정 / 기수", "이름 또는 업체명", "금액·기간", "계약서·담당", "확인"] as const;

/**
 * 계약 추가 위저드 (F96): 넓은 슬라이드 패널 안 5단계.
 * 종류·과정 / 기수 → 이름 또는 업체명 → 금액·기간 → 계약서·담당 → 확인([초안으로 저장]·[진행 시작])
 */
export function ContractWizard({
  scope,
  onDone,
}: {
  /** 상단에서 고른 과정·기수 (미리 채운다) */
  scope: { bootcampId?: string; cohortId?: string };
  onDone: (saved?: Contract) => void;
}) {
  const access = useQuery(staffAccessQuery);
  const canPickMentor = !!access.data && hasPermission(access.data, "educator.mentor.read");
  const form = useForm<ContractValues>({
    resolver: zodResolver(contractSchema),
    defaultValues: { ...emptyValues(scope), mentor_choice: canPickMentor ? "existing" : "new" },
  });
  const [step, setStep] = useState(0);
  const [file, setFile] = useState<ContractFile | null>(null);
  const [uploading, setUploading] = useState(false);
  const me = useQuery(managerCandidatesQuery(""));
  const [chosen, setChosen] = useState<ManagerChoice | null>(null);
  const meChoice = me.data?.find((m) => m.is_me);
  const manager = chosen ?? (meChoice ? { id: meChoice.employee_id, name: meChoice.name } : null);
  const create = useCreateContract();
  const [error, setError] = useState<string | null>(null);
  const dirty = form.formState.isDirty || !!file;
  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !create.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });
  const values = useWatch({ control: form.control });
  const cohorts = access.data?.cohorts ?? [];
  const bootcampName = cohorts.find((c) => c.bootcamp_id === values.bootcamp_id)?.bootcamp_name;
  const cohortNumber = cohorts.find((c) => c.id === values.cohort_id)?.cohort_number;
  const academy = bootcampName ? `${bootcampName} / ${cohortNumber ? `${cohortNumber}기` : "공통"}` : "";

  const next = async () => {
    setError(null);
    const fields = STEP_FIELDS[step];
    if (fields && !(await form.trigger(fields))) return;
    if (step === 3 && !manager) {
      setError("담당 직원을 골라 주세요.");
      return;
    }
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const submit = async (start: boolean) => {
    setError(null);
    if (!(await form.trigger()) || !manager) {
      setError("입력값을 다시 확인해 주세요.");
      return;
    }
    try {
      const result = await create.mutateAsync({
        body: fieldsOf(form.getValues(), { manager_employee_id: manager.id, contract_file_id: file?.id ?? null }),
        start,
      });
      form.reset(form.getValues());
      setFile(null);
      if (start && !result.started)
        toast.warning(`초안으로 저장했지만 진행을 시작하지 못했어요. ${contractError(result.error)}`);
      else toast.success(start ? "계약을 만들고 진행을 시작했어요" : "계약을 초안으로 저장했어요");
      onDone(result.saved);
    } catch (e) {
      setError(contractError(e));
    }
  };

  const vendor = values.contract_type ? isVendor(values.contract_type) : false;
  const amountPreview = values.contract_type
    ? (() => {
        const f = fieldsOf(form.getValues(), { manager_employee_id: "", contract_file_id: null });
        const amounts = {
          contract_type: f.contract_type,
          settlement_type: f.settlement_type,
          total_amount: f.total_amount ?? null,
          unit_price: f.unit_price ?? null,
          price_unit: f.price_unit ?? null,
          no_show_pay_amount: f.no_show_pay_amount ?? null,
          vat_type: f.vat_type ?? "NOT_APPLICABLE",
        };
        return { main: amountText(amounts), sub: amountSub(amounts) };
      })()
    : null;

  return (
    <>
      <PanelHead title="계약 추가" description={academy || "종류와 과정 / 기수부터 골라요"} onClose={() => onDone()} />
      <ol aria-label="단계" className="grid grid-cols-5 border-b border-border bg-card px-4 pt-4 pb-3.5">
        {STEPS.map((label, i) => {
          const done = i < step;
          const current = i === step;
          return (
            <li
              key={label}
              aria-current={current ? "step" : undefined}
              className="relative flex flex-col items-center gap-1.5 text-center"
            >
              {i > 0 ? (
                <span
                  aria-hidden
                  className={cn(
                    "absolute top-3.5 right-1/2 h-0.5 w-full -translate-y-1/2 rounded-full",
                    i <= step ? "bg-primary" : "bg-border",
                  )}
                />
              ) : null}
              <span
                className={cn(
                  "relative z-10 flex size-7 items-center justify-center rounded-full border-2 text-caption-strong transition-colors",
                  done
                    ? "border-primary bg-primary text-primary-foreground"
                    : current
                      ? "border-primary bg-card text-primary-text ring-4 ring-primary/15"
                      : "border-border bg-card text-muted-foreground",
                )}
              >
                {done ? <Check aria-hidden className="size-3.5" /> : i + 1}
              </span>
              <span
                className={cn(
                  "text-caption whitespace-nowrap",
                  current
                    ? "text-caption-strong text-primary-text"
                    : done
                      ? "text-foreground"
                      : "text-muted-foreground",
                )}
              >
                {label}
              </span>
            </li>
          );
        })}
      </ol>
      <form
        aria-label="계약 추가"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          if (step < STEPS.length - 1) void next();
        }}
        className="flex min-h-0 flex-1 flex-col"
      >
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto bg-muted/30 p-6">
          {step === 0 ? <BasicsSection form={form} cohorts={cohorts} /> : null}
          {step === 1 ? <PartySection form={form} mode="create" canPickMentor={canPickMentor} /> : null}
          {step === 2 ? (
            <>
              <AmountSection form={form} />
              <PeriodSection form={form} />
            </>
          ) : null}
          {step === 3 ? (
            <>
              <PanelSection title="계약서" icon={FileText}>
                <PanelRow label="파일" help={FILE_HELP}>
                  <FilePicker value={file} onChange={setFile} onUploading={setUploading} />
                </PanelRow>
              </PanelSection>
              <PanelSection title="담당" icon={UserRound}>
                <PanelRow label="담당 직원" top>
                  <div className="flex flex-col gap-2">
                    <span>{manager ? manager.name : "고르지 않음"}</span>
                    <ManagerList value={manager} onChange={setChosen} />
                  </div>
                </PanelRow>
              </PanelSection>
            </>
          ) : null}
          {step === 4 ? (
            <>
              <PanelSection title="확인" icon={ClipboardCheck}>
                <PanelRow label="종류">
                  {values.contract_type ? <ContractTypeBadge type={values.contract_type} /> : "—"}
                </PanelRow>
                <PanelRow label="과정 / 기수">{academy}</PanelRow>
                <PanelRow label="계약 명칭">{values.title}</PanelRow>
                <PanelRow label={vendor ? "업체명" : "이름"}>
                  {values.contract_type === "MENTOR" && values.mentor_choice === "existing"
                    ? values.mentor_label
                    : values.contractor_name}
                </PanelRow>
                {values.contractor_phone ? (
                  <PanelRow label={vendor ? "전화" : "휴대폰"}>
                    {maskPhone(values.contractor_phone) ?? values.contractor_phone}
                  </PanelRow>
                ) : null}
                <PanelRow label="금액">
                  {amountPreview?.main}
                  <span className="block text-caption font-normal text-muted-foreground">{amountPreview?.sub}</span>
                </PanelRow>
                <PanelRow label="기간">
                  {period({ start_date: values.start_date || null, end_date: values.end_date || null })}
                </PanelRow>
                <PanelRow label="계약서">{file ? file.file_name : "없음"}</PanelRow>
                <PanelRow label="담당 직원">{manager?.name ?? "—"}</PanelRow>
              </PanelSection>
              <p className="text-body-sm text-muted-foreground">
                [초안으로 저장]은 나중에 고쳐서 진행할 수 있어요. [진행 시작]은 계약서가 있어야 하고, 저장한 뒤 바로
                '진행 중'이 돼요.
              </p>
            </>
          ) : null}
          {error ? <Alert variant="error" title={error} /> : null}
        </div>
        <div className="flex items-center gap-2 border-t border-border bg-card px-6 py-3">
          <Button type="button" variant="ghost" onClick={() => onDone()}>
            취소
          </Button>
          <div className="flex-1" />
          {step > 0 ? (
            <Button type="button" variant="outline" onClick={() => setStep((s) => s - 1)}>
              이전
            </Button>
          ) : null}
          {step < STEPS.length - 1 ? (
            <Button type="submit" disabled={uploading}>
              다음 · {STEPS[step + 1]}
            </Button>
          ) : (
            <>
              <Button type="button" variant="outline" disabled={create.isPending} onClick={() => void submit(false)}>
                초안으로 저장
              </Button>
              <Button type="button" disabled={create.isPending || !file} onClick={() => void submit(true)}>
                진행 시작
              </Button>
            </>
          )}
        </div>
        <DiscardDialog blocker={blocker} />
      </form>
    </>
  );
}
