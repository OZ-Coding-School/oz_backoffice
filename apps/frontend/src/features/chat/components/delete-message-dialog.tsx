import { TriangleAlert } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

import { useDeleteMessage, type ChatMessage } from "../api";

/** 메시지 삭제 확인 (Figma `Screen / 채팅 · 메시지 삭제`, A57: 본문을 비우고 '삭제된 메시지'로 남는다) */
export function DeleteMessageDialog({
  threadId,
  message,
  onClose,
}: {
  threadId: string;
  message: ChatMessage | null;
  onClose: () => void;
}) {
  const remove = useDeleteMessage(threadId);
  const confirm = async () => {
    if (!message) return;
    try {
      await remove.mutateAsync(message.id);
      onClose();
    } catch {
      toast.error("메시지를 삭제하지 못했어요.");
    }
  };
  return (
    <Dialog open={!!message} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-120 flex-col gap-4 p-6">
        <div className="flex items-center gap-2.5 pr-8">
          <span
            aria-hidden
            className="inline-flex size-8 items-center justify-center rounded-full bg-destructive-subtle"
          >
            <TriangleAlert className="size-4 text-destructive-text" />
          </span>
          <DialogTitle className="text-h2 text-foreground">메시지를 삭제할까요?</DialogTitle>
        </div>
        <div className="flex flex-col gap-1 rounded-lg border border-border bg-muted px-4 py-3">
          <p className="line-clamp-3 text-body-strong break-words whitespace-pre-wrap text-foreground">
            {message?.body}
          </p>
          <DialogDescription className="text-caption text-muted-foreground">
            삭제하면 '삭제된 메시지입니다'로 보이고 되돌릴 수 없어요
          </DialogDescription>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            취소
          </Button>
          <Button variant="destructive" onClick={() => void confirm()} disabled={remove.isPending}>
            삭제
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
