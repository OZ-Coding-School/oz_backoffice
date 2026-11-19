import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { TriangleAlert, Wallet } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { FormField } from "@/components/form-field";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { formatKst, formatKstDay, formatMinutes } from "@/lib/datetime";

import { requestKeys, useCancelRequest, type MentoringRequest } from "../api";
import { CANCEL_ERROR_MESSAGES, CANCEL_FALLBACK_MESSAGE } from "../messages";
import { cancelSchema, REASON_MAX_LENGTH, type CancelForm } from "../schemas";

/** 신청 취소 확인 (Figma `Screen / 신청 취소 확인`, A42·M26·F29). 사유는 멘토에게 보인다. */
export function CancelRequestDialog({
  request,
  open,
  onOpenChange,
}: {
  request: MentoringRequest;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const cancel = useCancelRequest(request.id);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<CancelForm>({ resolver: zodResolver(cancelSchema), defaultValues: { reason: "" } });
  const reasonText = useWatch({ control: form.control, name: "reason" });

  const close = (next: boolean) => {
    if (!next) {
      form.reset();
      setServerError(null);
    }
    onOpenChange(next);
  };

  const submit = form.handleSubmit(async ({ reason }) => {
    setServerError(null);
    try {
      await cancel.mutateAsync(reason);
      toast.success("신청을 취소했어요");
      close(false);
    } catch (error) {
      const code = error instanceof ApiError ? error.code : undefined;
      if (code === "request_not_cancelable") void queryClient.invalidateQueries({ queryKey: requestKeys.all });
      setServerError((code && CANCEL_ERROR_MESSAGES[code]) ?? CANCEL_FALLBACK_MESSAGE);
    }
  });

  const approved = request.status === "APPROVED";
  const minutes = formatMinutes(request.duration);
  const first = request.session?.starts_at ?? request.desired_times[0];
  const more = !approved && request.desired_times.length > 1 ? ` 외 ${request.desired_times.length - 1}개` : "";

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="flex max-w-130 flex-col gap-4 p-6">
        <div className="flex items-center gap-2.5 pr-8">
          <span
            aria-hidden
            className="inline-flex size-8 items-center justify-center rounded-full bg-destructive-subtle"
          >
            <TriangleAlert className="size-4 text-destructive-text" />
          </span>
          <DialogTitle className="text-h2 text-foreground">이 신청을 취소할까요?</DialogTitle>
        </div>
        <div className="flex flex-col gap-1 rounded-lg border border-border bg-muted px-4 py-3">
          <p className="text-body-strong text-foreground">{request.topic}</p>
          <DialogDescription className="text-caption text-muted-foreground">
            {request.mentor_display_name} · {request.team_id ? "팀" : "1:1"} · {approved ? "확정" : "희망"}{" "}
            {first ? `${formatKstDay(first)} ${formatKst(first, "HH:mm")}` : ""}
            {more}
          </DialogDescription>
        </div>
        <form id="cancel-request" onSubmit={(e) => void submit(e)} className="flex flex-col gap-2">
          <FormField label="취소 사유 (멘토에게 보여요)" error={form.formState.errors.reason?.message}>
            {(field) => <Textarea {...field} maxLength={REASON_MAX_LENGTH} rows={3} {...form.register("reason")} />}
          </FormField>
          <p className="self-end text-caption text-muted-foreground">
            {reasonText.length} / {REASON_MAX_LENGTH}
          </p>
        </form>
        <p className="flex items-start gap-2 rounded-md bg-success-subtle px-3 py-2 text-body-sm text-foreground">
          <Wallet aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          {approved
            ? `차감된 ${minutes}을 모두 돌려받아요. 취소 후에는 되돌릴 수 없어요`
            : `차감 예정이던 ${minutes}을 바로 돌려받아요. 취소 후에는 되돌릴 수 없어요`}
        </p>
        {serverError ? <Alert variant="error" title={serverError} /> : null}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => close(false)}>
            돌아가기
          </Button>
          <Button type="submit" form="cancel-request" variant="destructive" disabled={cancel.isPending}>
            신청 취소
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
