import { useState } from "react";
import { toast } from "sonner";

import { Inbox } from "lucide-react";
import { CardTitle } from "@/components/section-card";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";

import { useSetAccepting } from "../api";
import { useScheduleScope } from "../scope";

interface AcceptingSetter {
  mutateAsync: (next: boolean) => Promise<{ canceled_pending_requests?: number }>;
  isPending: boolean;
}

/**
 * 신청 받기 (F52): 끌 때만 확인 창, 켜기는 바로. 일정 화면과 멘토 홈(F57)이 같이 쓴다.
 * 운영진 멘토 상세(F79)는 `setter`로 운영진 API를 넘기고, 바꿀 권한이 없으면 `readOnly`
 */
export function AcceptingCard({
  accepting,
  description = "끄면 새 신청만 막아요. 이미 받은 신청과 세션은 그대로예요.",
  setter,
  readOnly = false,
}: {
  accepting: boolean;
  description?: string;
  setter?: AcceptingSetter;
  readOnly?: boolean;
}) {
  const scope = useScheduleScope();
  const mine = useSetAccepting(scope.mentorId);
  const set: AcceptingSetter = setter ?? mine;
  const [confirming, setConfirming] = useState(false);
  const change = async (next: boolean) => {
    try {
      const result = await set.mutateAsync(next);
      setConfirming(false);
      toast.success(
        next
          ? "신청 받기를 켰어요"
          : (result.canceled_pending_requests ?? 0) > 0
            ? `신청 받기를 껐어요. 대기 중인 신청 ${result.canceled_pending_requests ?? 0}건을 취소했어요`
            : "신청 받기를 껐어요",
      );
    } catch {
      toast.error("신청 받기를 바꾸지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  };
  return (
    <section
      aria-labelledby="accepting-title"
      className="flex items-center gap-4 rounded-2xl border border-border bg-card shadow-sm p-4 md:p-5"
    >
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <CardTitle icon={Inbox} id="accepting-title">
          신청 받기
        </CardTitle>
        <p className="text-body-sm text-muted-foreground">{description}</p>
      </div>
      <label className="inline-flex shrink-0 items-center gap-2 text-body text-foreground">
        <Switch
          aria-labelledby="accepting-title"
          checked={accepting}
          disabled={set.isPending || readOnly}
          onCheckedChange={(next) => (next ? void change(true) : setConfirming(true))}
        />
        {accepting ? "받는 중" : "받지 않음"}
      </label>
      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent className="flex max-w-110 flex-col gap-4 p-6">
          <DialogTitle className="text-h2 text-foreground">신청 받기를 끌까요?</DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            새 신청을 받지 않아요. 대기 중인 신청은 자동으로 취소되고 신청자에게 시간이 돌아가요. 이미 승인한 세션은
            그대로예요.
          </DialogDescription>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              돌아가기
            </Button>
            <Button variant="destructive" disabled={set.isPending} onClick={() => void change(false)}>
              끄기
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
