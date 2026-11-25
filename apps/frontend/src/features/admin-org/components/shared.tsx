import type { useBlocker } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

/** 저장하지 않고 닫거나 옮길 때 확인 (F68) */
export function DiscardDialog({ blocker }: { blocker: ReturnType<typeof useBlocker> }) {
  return (
    <Dialog open={blocker.status === "blocked"} onOpenChange={(open) => (open ? undefined : blocker.reset?.())}>
      <DialogContent className="flex max-w-110 flex-col gap-4 p-6">
        <DialogTitle className="text-h2 text-foreground">저장하지 않은 변경이 있어요</DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">닫으면 고친 내용이 사라져요.</DialogDescription>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => blocker.reset?.()}>
            계속 고치기
          </Button>
          <Button variant="destructive" onClick={() => blocker.proceed?.()}>
            버리고 닫기
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
