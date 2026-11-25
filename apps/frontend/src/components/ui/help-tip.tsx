import { CircleHelp } from "lucide-react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { useRef, useState } from "react";

import { cn } from "@/lib/utils";

/**
 * 라벨 옆 `?` 아이콘 (F68). 마우스를 올리거나 누르면(키보드는 Enter·Space) 설명이 보인다.
 * 늘 보이는 설명 문장 대신 쓴다.
 */
export function HelpTip({ label, children, className }: { label: string; children: string; className?: string }) {
  const [open, setOpen] = useState(false);
  // 누르면 고정: 마우스를 떼도 닫히지 않고, 다시 누르거나 바깥을 누르면 닫힌다
  const [pinned, setPinned] = useState(false);
  const closing = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hover = (next: boolean) => {
    if (closing.current) clearTimeout(closing.current);
    if (next) setOpen(true);
    else if (!pinned) closing.current = setTimeout(() => setOpen(false), 120);
  };
  const change = (next: boolean) => {
    setOpen(next);
    if (!next) setPinned(false);
  };
  return (
    <PopoverPrimitive.Root open={open} onOpenChange={change}>
      <PopoverPrimitive.Trigger
        type="button"
        aria-label={`${label} 설명`}
        onPointerEnter={(e) => e.pointerType === "mouse" && hover(true)}
        onPointerLeave={(e) => e.pointerType === "mouse" && hover(false)}
        onClick={(e) => {
          // 마우스로 이미 열린 설명을 누르면 닫지 않고 고정한다
          if (open && !pinned) {
            e.preventDefault();
            setPinned(true);
          }
        }}
        className={cn(
          "inline-flex size-4 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
          className,
        )}
      >
        <CircleHelp aria-hidden className="size-3.5" />
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          side="top"
          align="start"
          sideOffset={6}
          onPointerEnter={() => hover(true)}
          onPointerLeave={() => hover(false)}
          onOpenAutoFocus={(e) => e.preventDefault()}
          className="z-50 max-w-70 rounded-lg border border-border bg-popover px-3 py-2 text-caption text-popover-foreground shadow-md outline-none"
        >
          {children}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
