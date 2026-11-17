import { X } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** shadcn Dialog를 Figma `Modal`(popover 배경·border·Shadow/lg·r12)에 맞췄다. */
export const Dialog = DialogPrimitive.Root;
export const DialogTitle = DialogPrimitive.Title;
export const DialogDescription = DialogPrimitive.Description;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  className,
  children,
  closeLabel = "닫기",
  ...props
}: ComponentProps<typeof DialogPrimitive.Content> & { closeLabel?: string; children: ReactNode }) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
      <DialogPrimitive.Content
        className={cn(
          "fixed inset-x-4 top-1/2 z-50 mx-auto max-h-[calc(100dvh-2rem)] -translate-y-1/2 overflow-y-auto",
          "rounded-xl border border-border bg-popover text-popover-foreground shadow-lg outline-none",
          className,
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close
          aria-label={closeLabel}
          className="absolute top-4 right-4 inline-flex size-8 items-center justify-center rounded-md text-foreground transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X aria-hidden className="size-4" />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
