import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { PanelHead, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { DiscardDialog } from "@/features/admin-org/components/shared";
import { kstDateKey } from "@/features/apply/slots";
import { staffAccessQuery } from "@/features/staff/api";

import { useAmendContract, useUpdateContract, type Contract, type ContractFile } from "../api";
import { amendmentOf, contractSchema, updateOf, valuesOf, type ContractValues } from "../contract-values";
import { academyText, contractError, FILE_HELP, STATUS, TYPE_LABELS } from "../labels";
import { AmountSection, BasicsSection, PartySection, PeriodSection } from "./contract-fields";
import { FilePicker } from "./file-picker";

const REASON_MAX = 500;

/**
 * 계약 수정 (F96, 같은 패널 편집 모드).
 * `edit`: 초안·진행 중은 모든 항목(종류는 그대로). `amend`: 계약 완료·이행 중은 변경 계약(A109⑨·A111⑤) —
 * 명칭·금액·기간·연락처만 + 변경 일자·사유(필수)·변경 계약서(선택).
 */
export function ContractEditForm({
  contract: c,
  mode,
  onDone,
}: {
  contract: Contract;
  mode: "edit" | "amend";
  onDone: () => void;
}) {
  const id = useId();
  const access = useQuery(staffAccessQuery);
  const form = useForm<ContractValues>({ resolver: zodResolver(contractSchema), defaultValues: valuesOf(c) });
  const update = useUpdateContract(c.id);
  const amend = useAmendContract(c.id);
  const [file, setFile] = useState<ContractFile | null>(mode === "edit" ? c.contract_file : null);
  const [uploading, setUploading] = useState(false);
  const [amendedOn, setAmendedOn] = useState(() => kstDateKey(new Date()));
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const fileChanged = mode === "edit" ? (file?.id ?? null) !== (c.contract_file?.id ?? null) : !!file;
  const dirty = form.formState.isDirty || fileChanged || !!reason;
  const saving = update.isPending || amend.isPending;
  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !saving,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });
  const status = STATUS[c.status];

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      if (mode === "edit") {
        const body = updateOf(c, v);
        if (fileChanged) body.contract_file_id = file?.id ?? null;
        if (Object.keys(body).length) await update.mutateAsync(body);
        toast.success("계약을 저장했어요");
      } else {
        if (!reason.trim()) {
          setError("변경 사유를 적어 주세요.");
          return;
        }
        if (!amendedOn) {
          setError("변경 일자를 골라 주세요.");
          return;
        }
        const changes = amendmentOf(c, v);
        if (!Object.keys(changes).length && !file) {
          setError("바뀐 항목이 없어요.");
          return;
        }
        await amend.mutateAsync({
          amended_on: amendedOn,
          reason: reason.trim(),
          changes,
          contract_file_id: file?.id ?? null,
        });
        toast.success("변경 계약을 등록했어요");
      }
      form.reset(v);
      setReason("");
      setFile(mode === "edit" ? file : null);
      onDone();
    } catch (e) {
      setError(contractError(e));
    }
  });

  return (
    <>
      <PanelHead
        title={c.title}
        description={`${TYPE_LABELS[c.contract_type]} · ${academyText(c, true)}`}
        badges={
          <>
            <Badge variant={status.badge}>{status.label}</Badge>
            <Badge variant="warning">{mode === "edit" ? "수정 중" : "변경 등록 중"}</Badge>
          </>
        }
        onClose={onDone}
      />
      <form
        aria-label={mode === "edit" ? "계약 수정" : "변경 등록"}
        noValidate
        onSubmit={(e) => void onSubmit(e)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
          {mode === "amend" ? (
            <PanelSection title="변경 계약">
              <PanelRow label="변경 일자" htmlFor={`${id}-on`}>
                <Input
                  id={`${id}-on`}
                  type="date"
                  className="w-44 font-normal"
                  value={amendedOn}
                  onChange={(e) => setAmendedOn(e.target.value)}
                />
              </PanelRow>
              <PanelRow label="사유" htmlFor={`${id}-reason`} top>
                <Textarea
                  id={`${id}-reason`}
                  rows={3}
                  maxLength={REASON_MAX}
                  placeholder="예: 12기 운영 범위 확대로 단가 조정"
                  className="font-normal"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </PanelRow>
              <PanelRow label="변경 계약서" help="선택. 변경 계약서를 올리면 변경 이력에서 볼 수 있어요.">
                <FilePicker value={file} onChange={setFile} onUploading={setUploading} label="변경 계약서 고르기" />
              </PanelRow>
            </PanelSection>
          ) : (
            <BasicsSection form={form} cohorts={access.data?.cohorts ?? []} lockType />
          )}
          {mode === "amend" ? (
            <PanelSection title="계약 정보">
              <PanelRow label="종류">{TYPE_LABELS[c.contract_type]}</PanelRow>
              <PanelRow label="과정 / 기수" help="종류·과정 / 기수는 변경 계약으로 바꿀 수 없어요.">
                {academyText(c, true)}
              </PanelRow>
              <PanelRow label="계약 명칭" htmlFor={`${id}-title`}>
                <Input id={`${id}-title`} maxLength={100} className="font-normal" {...form.register("title")} />
              </PanelRow>
            </PanelSection>
          ) : null}
          <PartySection form={form} mode={mode} canPickMentor={false} />
          <AmountSection form={form} />
          <PeriodSection form={form} />
          {mode === "edit" ? (
            <PanelSection title="계약서">
              <PanelRow label="파일" help={FILE_HELP}>
                <FilePicker
                  value={file}
                  onChange={setFile}
                  onUploading={setUploading}
                  removable={c.status === "DRAFT"}
                />
              </PanelRow>
            </PanelSection>
          ) : null}
          {error ? <Alert variant="error" title={error} /> : null}
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-6 py-3">
          <Button type="button" variant="outline" onClick={onDone}>
            취소
          </Button>
          <Button type="submit" disabled={saving || uploading}>
            {mode === "edit" ? "저장" : "변경 등록"}
          </Button>
        </div>
        <DiscardDialog blocker={blocker} />
      </form>
    </>
  );
}
