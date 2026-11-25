import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useId, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { PanelHead, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { Spinner } from "@/components/ui/spinner";
import { DiscardDialog } from "@/features/admin-org/components/shared";
import { maskPhone } from "@/features/profile/mask";

import {
  managerCandidatesQuery,
  uploadContractFile,
  useCreateContract,
  useUpdateContract,
  type Contract,
  type ContractFile,
  type ContractUpdate,
  type EducatorType,
} from "../api";
import { contractError, FILE_HELP, fileSize, linkedText, MENTOR_HELP, NEW_MENTOR_HELP } from "../labels";
import { ManagerList, type ManagerChoice } from "./pickers";

const MAX_BYTES = 10 * 1024 * 1024;
const TYPES = [
  { value: "MENTOR", label: "멘토" },
  { value: "INSTRUCTOR", label: "강사" },
] as const satisfies readonly { value: EducatorType; label: string }[];

const schema = z
  .object({
    educator_type: z.enum(["MENTOR", "INSTRUCTOR"]),
    contractor_name: z.string().trim().min(1, "계약자 이름을 적어 주세요").max(50, "50자까지 적을 수 있어요"),
    contractor_phone: z
      .string()
      .trim()
      .regex(/^01[0-9]-?\d{3,4}-?\d{4}$/, "휴대폰 번호를 확인해 주세요"),
    contractor_email: z
      .string()
      .trim()
      .max(255)
      .refine((v) => !v || z.email().safeParse(v).success, "이메일을 확인해 주세요"),
    title: z.string().trim().min(1, "제목을 적어 주세요").max(100, "100자까지 적을 수 있어요"),
    start_date: z.string().min(1, "시작일을 골라 주세요"),
    end_date: z.string().min(1, "종료일을 골라 주세요"),
  })
  .refine((v) => !v.start_date || !v.end_date || v.end_date >= v.start_date, {
    path: ["end_date"],
    message: "종료일은 시작일과 같거나 뒤여야 해요",
  });
type Values = z.infer<typeof schema>;

const valuesOf = (c?: Contract): Values => ({
  educator_type: c?.educator_type ?? "MENTOR",
  contractor_name: c?.contractor_name ?? "",
  contractor_phone: c?.contractor_phone ?? "",
  contractor_email: c?.contractor_email ?? "",
  title: c?.title ?? "",
  start_date: c?.start_date ?? "",
  end_date: c?.end_date ?? "",
});

const dot = (d: string) => d.replaceAll("-", ".");

/**
 * 계약 추가·수정 (F83·F68·F85): 조회와 같은 섹션·줄에서 값 자리만 입력 칸.
 * 작성 중이면 모든 항목, 확정한 계약은 담당 직원만 바꾼다(A25). 유형은 추가 때만(세그먼트).
 */
export function ContractForm({
  contract,
  title,
  description,
  badge,
  onDone,
}: {
  contract?: Contract;
  /** 패널 머리 */
  title: string;
  description: string;
  /** 머리의 상태 배지 (수정 모드면 '수정 중'을 더한다) */
  badge?: ReactNode;
  onDone: (saved?: Contract) => void;
}) {
  const id = useId();
  const isNew = !contract;
  const editable = isNew || contract.status === "DRAFT";
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: valuesOf(contract) });
  const create = useCreateContract();
  const update = useUpdateContract(contract?.id ?? "");
  const [file, setFile] = useState<ContractFile | null>(contract?.contract_file ?? null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const me = useQuery({ ...managerCandidatesQuery(""), enabled: isNew });
  const [chosen, setChosen] = useState<ManagerChoice | null>(null);
  const meChoice = me.data?.find((m) => m.is_me);
  const current: ManagerChoice | null = contract
    ? { id: contract.manager_employee_id, name: contract.manager_name ?? "—" }
    : meChoice
      ? { id: meChoice.employee_id, name: meChoice.name }
      : null;
  const manager = chosen ?? current;
  const fileChanged = (file?.id ?? null) !== (contract?.contract_file?.id ?? null);
  const managerChanged = chosen !== null && chosen.id !== contract?.manager_employee_id;
  const dirty = form.formState.isDirty || fileChanged || managerChanged;
  const saving = create.isPending || update.isPending;
  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !saving,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });
  const { errors } = form.formState;
  const educatorType = useWatch({ control: form.control, name: "educator_type" });

  const onPick = async (e: ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0];
    e.target.value = "";
    if (!picked) return;
    if (picked.type !== "application/pdf" && !picked.name.toLowerCase().endsWith(".pdf")) {
      toast.error("PDF 파일만 올릴 수 있어요.");
      return;
    }
    if (picked.size > MAX_BYTES) {
      toast.error("10MB까지 올릴 수 있어요.");
      return;
    }
    setUploading(true);
    try {
      setFile(await uploadContractFile(picked));
    } catch (err) {
      toast.error(contractError(err));
    } finally {
      setUploading(false);
    }
  };

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    const email = v.contractor_email.trim() || null;
    try {
      if (isNew) {
        if (!manager) {
          setError("담당 직원을 골라 주세요.");
          return;
        }
        const saved = await create.mutateAsync({
          educator_type: v.educator_type,
          contractor_name: v.contractor_name.trim(),
          contractor_phone: v.contractor_phone.trim(),
          contractor_email: email,
          title: v.title.trim(),
          start_date: v.start_date,
          end_date: v.end_date,
          manager_employee_id: manager.id,
          contract_file_id: file?.id ?? null,
        });
        form.reset(v);
        toast.success("계약을 작성 중으로 저장했어요");
        onDone(saved);
        return;
      }
      const c = contract;
      const body: ContractUpdate = {};
      if (editable) {
        if (v.contractor_name.trim() !== c.contractor_name) body.contractor_name = v.contractor_name.trim();
        if (v.contractor_phone.trim() !== c.contractor_phone) body.contractor_phone = v.contractor_phone.trim();
        if (email !== (c.contractor_email ?? null)) body.contractor_email = email;
        if (v.title.trim() !== c.title) body.title = v.title.trim();
        if (v.start_date !== c.start_date) body.start_date = v.start_date;
        if (v.end_date !== c.end_date) body.end_date = v.end_date;
        if (fileChanged) body.contract_file_id = file?.id ?? null;
      }
      if (managerChanged && chosen) body.manager_employee_id = chosen.id;
      const saved = Object.keys(body).length ? await update.mutateAsync(body) : c;
      form.reset(v);
      toast.success("계약을 저장했어요");
      onDone(saved);
    } catch (e) {
      setError(contractError(e));
    }
  });

  const field = (name: keyof Values, label: string, text: string, props: Record<string, unknown> = {}) =>
    editable ? (
      <PanelRow label={label} htmlFor={`${id}-${name}`} top={!!errors[name]}>
        <Input
          id={`${id}-${name}`}
          aria-invalid={!!errors[name]}
          className="font-normal"
          {...props}
          {...form.register(name)}
        />
        {errors[name] ? (
          <p className="mt-1 text-caption font-normal text-destructive-text">{errors[name]?.message}</p>
        ) : null}
      </PanelRow>
    ) : (
      <PanelRow label={label}>{text}</PanelRow>
    );

  const linked = contract ? linkedText(contract) : null;
  return (
    <>
      <PanelHead
        title={title}
        description={description}
        badges={
          isNew ? null : (
            <>
              {badge}
              <Badge variant="warning">수정 중</Badge>
            </>
          )
        }
        onClose={() => onDone()}
      />
      <form
        aria-label={isNew ? "계약 추가" : "계약 수정"}
        noValidate
        onSubmit={(e) => void onSubmit(e)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
          <PanelSection title="계약 정보">
            {isNew ? (
              <PanelRow label="유형">
                <Controller
                  control={form.control}
                  name="educator_type"
                  render={({ field: f }) => (
                    <Segmented label="유형" value={f.value} onChange={f.onChange} options={TYPES} />
                  )}
                />
              </PanelRow>
            ) : null}
            {field("contractor_name", "계약자", contract?.contractor_name ?? "", { maxLength: 50 })}
            {field("contractor_phone", "휴대폰", maskPhone(contract?.contractor_phone) ?? "", {
              inputMode: "tel",
              placeholder: "010-0000-0000",
            })}
            {field("contractor_email", "이메일", contract?.contractor_email ?? "—", {
              type: "email",
              maxLength: 255,
              placeholder: "선택",
            })}
            {field("title", "제목", contract?.title ?? "", { maxLength: 100 })}
            {field("start_date", "시작일", dot(contract?.start_date ?? ""), { type: "date" })}
            {field("end_date", "종료일", dot(contract?.end_date ?? ""), { type: "date" })}
          </PanelSection>
          <PanelSection title="계약서">
            <PanelRow label="파일" help={FILE_HELP}>
              {editable ? (
                <div className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate font-normal">
                    {file ? (
                      `${file.file_name} · ${fileSize(file.file_size)}`
                    ) : (
                      <span className="text-muted-foreground">없음</span>
                    )}
                  </span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={uploading}
                    onClick={() => fileRef.current?.click()}
                  >
                    {uploading ? <Spinner className="size-4" /> : null}
                    {file ? "다른 파일" : "파일 고르기"}
                  </Button>
                  {file ? (
                    <Button type="button" variant="ghost" size="sm" onClick={() => setFile(null)}>
                      빼기
                    </Button>
                  ) : null}
                </div>
              ) : (
                (file?.file_name ?? "없음")
              )}
              <input
                ref={fileRef}
                type="file"
                accept="application/pdf,.pdf"
                className="sr-only"
                tabIndex={-1}
                aria-label="계약서 고르기"
                onChange={(e) => void onPick(e)}
              />
            </PanelRow>
          </PanelSection>
          {isNew ? (
            educatorType === "MENTOR" ? (
              <PanelSection title="멘토">
                <PanelRow label="멘토" help={NEW_MENTOR_HELP}>
                  <span className="font-normal text-muted-foreground">계약자 이름·휴대폰으로 정해져요</span>
                </PanelRow>
              </PanelSection>
            ) : null
          ) : (
            <PanelSection title={contract.educator_type === "MENTOR" ? "멘토" : "강사"}>
              <PanelRow label={contract.educator_type === "MENTOR" ? "멘토" : "강사"} help={MENTOR_HELP}>
                {linked?.text}
              </PanelRow>
            </PanelSection>
          )}
          <PanelSection title="담당">
            <PanelRow label="담당 직원" top>
              <div className="flex flex-col gap-2">
                <span>{manager ? manager.name : "고르지 않음"}</span>
                <ManagerList value={manager} onChange={setChosen} />
              </div>
            </PanelRow>
          </PanelSection>
          {error ? <Alert variant="error" title={error} /> : null}
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-6 py-3">
          <Button type="button" variant="outline" onClick={() => onDone()}>
            취소
          </Button>
          <Button type="submit" disabled={saving || uploading}>
            {isNew ? "추가" : "저장"}
          </Button>
        </div>
        <DiscardDialog blocker={blocker} />
      </form>
    </>
  );
}
