import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { CircleX, Info } from "lucide-react";
import { RadioGroup as RadioGroupPrimitive } from "radix-ui";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { FormField } from "@/components/form-field";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { requestKeys, type MentoringRequest } from "@/features/requests/api";
import { REASON_MAX_LENGTH } from "@/features/requests/schemas";
import { formatKst, formatKstDay, formatMinutes } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { useApproveRequest, useRejectRequest } from "../api";
import {
  APPROVE_ERROR_MESSAGES,
  APPROVE_FALLBACK_MESSAGE,
  REJECT_ERROR_MESSAGES,
  REJECT_FALLBACK_MESSAGE,
  SLOT_CONFLICT_CODES,
  SLOT_PASSED_CODE,
} from "../messages";
import { rejectSchema, type RejectForm } from "../schemas";

type SlotBlock = "passed" | "conflict";

/**
 * 진행할 일시를 골라 승인 (F45·A43). 희망 일시는 순위대로, 시작한 일시는 비활성이다.
 * 처음 고른 값은 남은 일시 중 가장 높은 순위. 승인이 겹침(409)이면 그 일시를 막는다.
 */
export function ApprovePanel({ request, now }: { request: MentoringRequest; now: number }) {
  const queryClient = useQueryClient();
  const approve = useApproveRequest(request.id);
  const [blocked, setBlocked] = useState<Record<string, SlotBlock>>({});
  const blockOf = (t: string): SlotBlock | undefined => blocked[t] ?? (Date.parse(t) <= now ? "passed" : undefined);
  const open = request.desired_times.filter((t) => !blockOf(t));
  const [picked, setPicked] = useState<string | undefined>(open[0]);
  const selected = picked && !blockOf(picked) ? picked : open[0];
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!selected) return;
    setError(null);
    try {
      await approve.mutateAsync(selected);
      toast.success("승인했어요. 세션과 Meet 링크가 만들어졌어요");
    } catch (e) {
      const code = e instanceof ApiError ? e.code : undefined;
      if (code && SLOT_CONFLICT_CODES.has(code)) setBlocked((b) => ({ ...b, [selected]: "conflict" }));
      else if (code === SLOT_PASSED_CODE) setBlocked((b) => ({ ...b, [selected]: "passed" }));
      else if (code === "request_not_pending")
        void queryClient.invalidateQueries({ queryKey: requestKeys.detail(request.id) });
      setError((code && APPROVE_ERROR_MESSAGES[code]) ?? APPROVE_FALLBACK_MESSAGE);
    }
  };

  return (
    <section
      aria-labelledby="approve-title"
      className="flex flex-col gap-3 rounded-2xl border border-border bg-card shadow-sm p-5"
    >
      <div className="flex flex-col gap-1">
        <h2 id="approve-title" className="text-h3 text-foreground">
          진행할 일시를 골라 승인해요
        </h2>
        <p className="text-caption text-muted-foreground">수강생이 고른 희망 일시예요</p>
      </div>
      {error ? (
        <Alert
          variant="error"
          title={error}
          description={open.length === 0 ? "승인할 수 있는 일시가 없어요. 사유와 함께 반려해 주세요." : undefined}
        />
      ) : null}
      <RadioGroupPrimitive.Root
        aria-label="희망 일시"
        value={selected ?? ""}
        onValueChange={setPicked}
        className="flex flex-col gap-2"
      >
        {request.desired_times.map((t, i) => {
          const block = blockOf(t);
          return (
            <label
              key={t}
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3",
                t === selected ? "border-2 border-primary bg-accent" : "border-border",
                block && "cursor-not-allowed opacity-60",
              )}
            >
              <RadioGroupPrimitive.Item
                value={t}
                disabled={!!block}
                aria-label={`${i + 1}순위 ${slotText(t, request.duration)}`}
                className="inline-flex size-4 shrink-0 items-center justify-center rounded-full border border-input bg-background outline-none focus-visible:ring-2 focus-visible:ring-ring data-[state=checked]:border-primary"
              >
                <RadioGroupPrimitive.Indicator className="size-2 rounded-full bg-primary" />
              </RadioGroupPrimitive.Item>
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="text-caption text-primary-text">{i + 1}순위</span>
                <span className="text-body-strong text-foreground">
                  {formatKstDay(t)}{" "}
                  <span className="font-mono font-normal">
                    {formatKst(t, "HH:mm")} ~ {formatKst(Date.parse(t) + request.duration * 60_000, "HH:mm")}
                  </span>
                </span>
                {block ? (
                  <span className="text-caption text-destructive-text">
                    {block === "passed" ? "지난 일시예요" : "다른 세션과 겹쳐요"}
                  </span>
                ) : null}
              </span>
            </label>
          );
        })}
      </RadioGroupPrimitive.Root>
      <p className="flex items-start gap-2 rounded-md bg-accent px-3 py-2 text-body-sm text-foreground">
        <Info aria-hidden className="mt-0.5 size-3.5 shrink-0" />
        승인하면 세션과 Meet 링크가 만들어지고, 신청자에게 채팅으로 안내돼요
      </p>
      <Button onClick={() => void submit()} disabled={!selected || approve.isPending}>
        이 일시로 승인
      </Button>
    </section>
  );
}

function slotText(iso: string, duration: number): string {
  return `${formatKstDay(iso)} ${formatKst(iso, "HH:mm")} ~ ${formatKst(Date.parse(iso) + duration * 60_000, "HH:mm")}`;
}

export function RejectPanel({ request }: { request: MentoringRequest }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="flex flex-col gap-2 rounded-2xl border border-border bg-card shadow-sm p-5">
      <h2 className="text-body-strong text-foreground">희망 일시에 진행이 어렵다면</h2>
      <p className="text-caption text-muted-foreground">사유와 함께 반려하면 신청자의 차감 예정 시간이 돌아가요</p>
      <Button variant="outline" className="text-destructive-text" onClick={() => setOpen(true)}>
        반려
      </Button>
      <RejectDialog request={request} open={open} onOpenChange={setOpen} />
    </section>
  );
}

/** 반려 확인 (Figma `상태 / 반려 확인 창`, A42·F45). 사유는 신청자에게 보인다 */
function RejectDialog({
  request,
  open,
  onOpenChange,
}: {
  request: MentoringRequest;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const reject = useRejectRequest(request.id);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<RejectForm>({ resolver: zodResolver(rejectSchema), defaultValues: { reason: "" } });
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
      await reject.mutateAsync(reason);
      toast.success("반려했어요");
      close(false);
    } catch (e) {
      const code = e instanceof ApiError ? e.code : undefined;
      if (code === "request_not_pending")
        void queryClient.invalidateQueries({ queryKey: requestKeys.detail(request.id) });
      setServerError((code && REJECT_ERROR_MESSAGES[code]) ?? REJECT_FALLBACK_MESSAGE);
    }
  });

  const [first, ...rest] = request.desired_times;
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="flex max-w-130 flex-col gap-4 p-6">
        <div className="flex items-center gap-2.5 pr-8">
          <span
            aria-hidden
            className="inline-flex size-8 items-center justify-center rounded-full bg-destructive-subtle"
          >
            <CircleX className="size-4 text-destructive-text" />
          </span>
          <DialogTitle className="text-h2 text-foreground">이 신청을 반려할까요?</DialogTitle>
        </div>
        <div className="flex flex-col gap-1 rounded-lg border border-border bg-muted px-4 py-3">
          <p className="text-body-strong text-foreground">{request.topic}</p>
          <DialogDescription className="text-caption text-muted-foreground">
            {request.team_id ? (request.team_label ?? "팀") : request.requester_name} · {request.team_id ? "팀" : "1:1"}
            {first ? ` · 희망 ${formatKstDay(first)} ${formatKst(first, "HH:mm")}` : ""}
            {rest.length ? ` 외 ${rest.length}개` : ""}
          </DialogDescription>
        </div>
        <form id="reject-request" onSubmit={(e) => void submit(e)} className="flex flex-col gap-2">
          <FormField label="반려 사유 (신청자에게 보여요)" error={form.formState.errors.reason?.message}>
            {(field) => <Textarea {...field} maxLength={REASON_MAX_LENGTH} rows={3} {...form.register("reason")} />}
          </FormField>
          <p className="self-end text-caption text-muted-foreground">
            {reasonText.length} / {REASON_MAX_LENGTH}
          </p>
        </form>
        <p className="flex items-start gap-2 rounded-md bg-accent px-3 py-2 text-body-sm text-foreground">
          <Info aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          신청자의 차감 예정 {formatMinutes(request.duration)}이 돌아가고, 사유는 채팅 안내에도 남아요
        </p>
        {serverError ? <Alert variant="error" title={serverError} /> : null}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => close(false)}>
            돌아가기
          </Button>
          <Button type="submit" form="reject-request" variant="destructive" disabled={reject.isPending}>
            반려하기
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
