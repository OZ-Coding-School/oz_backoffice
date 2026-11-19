import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/** Figma `Components / Textarea`. 입력 칸 스타일은 Input과 같다(테두리·포커스·오류는 `aria-invalid`). */
export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "min-h-24 w-full min-w-0 resize-y rounded-md border border-input bg-background px-3 py-2 text-body text-foreground transition-colors",
        "placeholder:text-muted-foreground",
        "outline-none focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring",
        "aria-invalid:border-destructive aria-invalid:focus-visible:ring-destructive",
        "disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground disabled:opacity-60",
        className,
      )}
      {...props}
    />
  );
}
