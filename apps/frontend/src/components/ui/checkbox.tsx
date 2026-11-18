import { Check } from "lucide-react";
import { Checkbox as CheckboxPrimitive } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/** Figma `Components / Checkbox` (16px 사각, 켜면 primary 배경·흰 체크, 라벨 Body/Default). */
export function Checkbox({
  className,
  children,
  ...props
}: ComponentProps<typeof CheckboxPrimitive.Root> & { children: string }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-body text-foreground has-disabled:cursor-not-allowed has-disabled:opacity-50">
      <CheckboxPrimitive.Root
        className={cn(
          "inline-flex size-4 shrink-0 items-center justify-center rounded-sm border border-input bg-background outline-none",
          "focus-visible:ring-2 focus-visible:ring-ring",
          "data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground",
          className,
        )}
        {...props}
      >
        <CheckboxPrimitive.Indicator>
          <Check className="size-3" strokeWidth={3} />
        </CheckboxPrimitive.Indicator>
      </CheckboxPrimitive.Root>
      {children}
    </label>
  );
}
