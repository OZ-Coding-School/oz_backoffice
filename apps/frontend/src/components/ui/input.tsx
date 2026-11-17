import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * Figma `Components / Input`의 입력 칸(Control). 라벨·도움말은 폼 필드 조각이 감싼다.
 * 오류 상태는 `aria-invalid`로 표시한다 (React Hook Form과 연결).
 */
export function Input({ className, type = "text", ...props }: ComponentProps<"input">) {
  return (
    <input
      data-slot="input"
      type={type}
      className={cn(
        "h-9 w-full min-w-0 rounded-md border border-input bg-background px-3 text-body text-foreground transition-colors",
        "placeholder:text-muted-foreground",
        "outline-none focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring",
        "aria-invalid:border-destructive aria-invalid:focus-visible:ring-destructive",
        "disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground disabled:opacity-60",
        "file:border-0 file:bg-transparent file:text-label",
        className,
      )}
      {...props}
    />
  );
}
