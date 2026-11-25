import { Dialog as SheetPrimitive } from "radix-ui";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * 오른쪽에서 밀려 나오는 패널 (F67). shadcn Sheet와 같은 구조로 radix Dialog를 쓴다.
 * 머리(제목·닫기)는 화면이 그린다: 편집 모드처럼 머리 구성이 바뀌기 때문이다.
 */
export const Sheet = SheetPrimitive.Root;
export const SheetTitle = SheetPrimitive.Title;
export const SheetDescription = SheetPrimitive.Description;
export const SheetClose = SheetPrimitive.Close;

export function SheetContent({
  className,
  children,
  ...props
}: ComponentProps<typeof SheetPrimitive.Content> & { children: ReactNode }) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Overlay className="fixed inset-0 z-50 bg-black/30 motion-safe:animate-overlay-in" />
      <SheetPrimitive.Content
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-110 max-w-full flex-col border-l border-border bg-card text-card-foreground shadow-lg outline-none",
          "motion-safe:animate-sheet-in",
          className,
        )}
        {...props}
      >
        {children}
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  );
}
