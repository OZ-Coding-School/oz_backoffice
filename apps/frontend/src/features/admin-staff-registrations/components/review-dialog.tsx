import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { StaffFields } from "@/features/auth/components/staff-fields";
import type { StaffOptions } from "@/features/auth/staff-api";
import { staffFormSchema, staffFormValues, staffPayload, type StaffFormValues } from "@/features/auth/staff-form";
import { staffAccessQuery } from "@/features/staff/api";
import { formatKst } from "@/lib/datetime";

import { openCohorts, useApproveRegistration, useRejectRegistration, type AdminRegistration } from "../api";

export const REJECT_REASON_MAX = 300;

/**
 * 운영진 신청 검토 (F61·A62): 신청 내용을 채운 폼을 고쳐 승인하거나, 같은 창에서 사유를 적어 반려한다.
 * '다른 팀 과정도 보기'를 켜면 모든 활성 과정과 진행 예정·진행 중 기수를 고를 수 있다(승인 조정 자유)
 */
export function ReviewDialog({
  registration,
  options,
  onClose,
}: {
  registration: AdminRegistration;
  options: StaffOptions;
  onClose: () => void;
}) {
  const access = useQuery(staffAccessQuery);
  const form = useForm<StaffFormValues>({
    resolver: zodResolver(staffFormSchema),
    defaultValues: staffFormValues(options, registration),
  });
  const [wide, setWide] = useState(false);
  const [mode, setMode] = useState<"review" | "reject">("review");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const approve = useApproveRegistration(registration.id);
  const reject = useRejectRegistration(registration.id);
  const name = registration.applicant?.name ?? "신청자";

  const onApprove = form.handleSubmit(async (values) => {
    setError(null);
    try {
      await approve.mutateAsync(staffPayload(options, values, wide));
      toast.success(`${name}님을 운영진으로 승인했어요`);
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "승인하지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  });

  const onReject = async () => {
    setError(null);
    try {
      await reject.mutateAsync(reason.trim());
      toast.success(`${name}님 신청을 반려했어요`);
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "반려하지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  };

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-h-[90dvh] max-w-150 flex-col gap-4 overflow-y-auto p-6">
        <div className="flex flex-col gap-1 pr-8">
          <DialogTitle className="text-h2 text-foreground">
            {mode === "review" ? `운영진 승인 · ${name}` : `운영진 신청 반려 · ${name}`}
          </DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            {mode === "review"
              ? "신청 내용을 확인하고 필요하면 고친 뒤 승인하세요. 고친 값으로 담당자가 등록돼요."
              : "반려 사유는 신청자 화면에 보여요. 신청자는 고쳐서 다시 신청할 수 있어요."}
          </DialogDescription>
        </div>
        <dl className="grid grid-cols-[auto_1fr_auto] gap-x-6 gap-y-0.5 rounded-lg bg-muted px-4 py-3">
          <dt className="text-caption text-muted-foreground">신청 이름</dt>
          <dt className="text-caption text-muted-foreground">이메일</dt>
          <dt className="text-caption text-muted-foreground">신청일</dt>
          <dd className="text-body-strong text-foreground">{name}</dd>
          <dd className="break-all text-body-strong text-foreground">{registration.applicant?.email ?? "—"}</dd>
          <dd className="text-body-strong text-foreground">
            {registration.created_at ? formatKst(registration.created_at, "yyyy.MM.dd") : "—"}
          </dd>
        </dl>
        {mode === "review" ? (
          <form aria-label="신청 내용" noValidate onSubmit={(e) => void onApprove(e)} className="flex flex-col gap-4">
            <StaffFields
              form={form}
              options={options}
              wide={wide}
              wideCohorts={openCohorts(access.data?.cohorts ?? [])}
              courseHelper={
                wide
                  ? "모든 활성 과정에서 골라 추가하세요. 추가한 과정의 운영 매니저로 등록돼요."
                  : "소속 팀이 담당하는 과정이 먼저 보여요. 다른 팀 과정은 아래 스위치를 켜면 고를 수 있어요."
              }
            />
            <label className="inline-flex w-fit items-center gap-2 text-body text-foreground">
              <Switch checked={wide} onCheckedChange={setWide} aria-label="다른 팀 과정도 보기" />
              다른 팀 과정도 보기
            </label>
            {error ? <Alert variant="error" title={error} /> : null}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setMode("reject")}>
                반려
              </Button>
              <Button type="submit" disabled={approve.isPending}>
                승인
              </Button>
            </div>
          </form>
        ) : (
          <>
            <div className="flex flex-col gap-1.5">
              <Textarea
                aria-label="반려 사유"
                placeholder="예: 담당 과정을 확인해 다시 신청해 주세요."
                value={reason}
                maxLength={REJECT_REASON_MAX}
                rows={4}
                onChange={(e) => setReason(e.target.value)}
              />
              <p className="text-right text-caption text-muted-foreground">
                {reason.length} / {REJECT_REASON_MAX}
              </p>
            </div>
            {error ? <Alert variant="error" title={error} /> : null}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setMode("review")}>
                돌아가기
              </Button>
              <Button
                variant="destructive"
                disabled={!reason.trim() || reject.isPending}
                onClick={() => void onReject()}
              >
                반려
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
