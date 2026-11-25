import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useId, useRef, useState, type ChangeEvent } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Spinner } from "@/components/ui/spinner";
import { DiscardDialog } from "@/features/admin-org/components/shared";

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
import { contractError, fileSize } from "../labels";
import { ManagerList, type ManagerChoice } from "./pickers";

const MAX_BYTES = 10 * 1024 * 1024;

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

/** 계약 추가·수정 폼 (F83): 수정은 작성 중일 때만, 담당 직원은 추가 때만(수정은 조회의 [변경]) */
export function ContractForm({ contract, onDone }: { contract?: Contract; onDone: (saved?: Contract) => void }) {
  const id = useId();
  const isNew = !contract;
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
  const manager = chosen ?? (meChoice ? { id: meChoice.employee_id, name: meChoice.name } : null);
  const fileChanged = (file?.id ?? null) !== (contract?.contract_file?.id ?? null);
  const dirty = form.formState.isDirty || fileChanged || (isNew && chosen !== null);
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
      if (v.contractor_name.trim() !== c.contractor_name) body.contractor_name = v.contractor_name.trim();
      if (v.contractor_phone.trim() !== c.contractor_phone) body.contractor_phone = v.contractor_phone.trim();
      if (email !== (c.contractor_email ?? null)) body.contractor_email = email;
      if (v.title.trim() !== c.title) body.title = v.title.trim();
      if (v.start_date !== c.start_date) body.start_date = v.start_date;
      if (v.end_date !== c.end_date) body.end_date = v.end_date;
      if (fileChanged) body.contract_file_id = file?.id ?? null;
      const saved = Object.keys(body).length ? await update.mutateAsync(body) : c;
      form.reset(v);
      setFile(saved.contract_file ?? null);
      toast.success("계약을 저장했어요");
      onDone(saved);
    } catch (e) {
      setError(contractError(e));
    }
  });

  const field = (name: keyof Values, label: string, props: Record<string, unknown> = {}) => (
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
  );

  return (
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
                  <RadioGroup
                    value={f.value}
                    onValueChange={(v) => f.onChange(v as EducatorType)}
                    aria-label="유형"
                    className="gap-6 font-normal"
                  >
                    <RadioGroupItem value="MENTOR">멘토</RadioGroupItem>
                    <RadioGroupItem value="INSTRUCTOR">강사</RadioGroupItem>
                  </RadioGroup>
                )}
              />
            </PanelRow>
          ) : null}
          {isNew && educatorType === "MENTOR" ? (
            <p className="text-caption text-muted-foreground">
              이름·휴대폰이 같은 멘토가 있으면 그 멘토에 붙고, 없으면 가입 전 멘토가 생겨요.
            </p>
          ) : null}
          {field("contractor_name", "계약자 이름", { maxLength: 50 })}
          {field("contractor_phone", "휴대폰", { inputMode: "tel", placeholder: "010-0000-0000" })}
          {field("contractor_email", "이메일 (선택)", { type: "email", maxLength: 255 })}
          {field("title", "제목", { maxLength: 100 })}
          {field("start_date", "시작일", { type: "date" })}
          {field("end_date", "종료일", { type: "date" })}
        </PanelSection>
        <PanelSection title="계약서 (PDF)">
          {file ? (
            <div className="flex items-center gap-3">
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-body-strong text-foreground">{file.file_name}</span>
                <span className="text-caption text-muted-foreground">{fileSize(file.file_size)} · 올림 완료</span>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={uploading}
                onClick={() => fileRef.current?.click()}
              >
                다른 파일
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => setFile(null)}>
                빼기
              </Button>
            </div>
          ) : (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="self-start"
              disabled={uploading}
              onClick={() => fileRef.current?.click()}
            >
              {uploading ? <Spinner className="size-4" /> : null}
              파일 고르기
            </Button>
          )}
          <p className="text-caption text-muted-foreground">PDF 10MB까지. 확정하려면 계약서가 있어야 해요.</p>
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            className="sr-only"
            tabIndex={-1}
            aria-label="계약서 고르기"
            onChange={(e) => void onPick(e)}
          />
        </PanelSection>
        {isNew ? (
          <PanelSection title="담당 직원">
            <p className="text-body-strong text-foreground">{manager ? manager.name : "고르지 않음"}</p>
            <ManagerList value={manager} onChange={setChosen} />
          </PanelSection>
        ) : null}
        {error ? <Alert variant="error" title={error} /> : null}
      </div>
      <div className="flex justify-end gap-2 border-t border-border px-6 py-3">
        <Button type="button" variant="outline" onClick={() => onDone()}>
          취소
        </Button>
        <Button type="submit" disabled={saving || uploading}>
          저장
        </Button>
      </div>
      <DiscardDialog blocker={blocker} />
    </form>
  );
}
