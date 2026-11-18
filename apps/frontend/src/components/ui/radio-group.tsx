import { RadioGroup as RadioGroupPrimitive } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/** Figma `Components / Radio` (16px 원, primary 테두리·점, 라벨 Body/Default). */
export function RadioGroup({ className, ...props }: ComponentProps<typeof RadioGroupPrimitive.Root>) {
  return <RadioGroupPrimitive.Root className={cn("flex gap-6", className)} {...props} />;
}

export function RadioGroupItem({
  className,
  children,
  ...props
}: ComponentProps<typeof RadioGroupPrimitive.Item> & { children: string }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-body text-foreground has-disabled:cursor-not-allowed has-disabled:opacity-50">
      <RadioGroupPrimitive.Item
        className={cn(
          "inline-flex size-4 shrink-0 items-center justify-center rounded-full border border-input bg-background outline-none",
          "focus-visible:ring-2 focus-visible:ring-ring data-[state=checked]:border-primary",
          className,
        )}
        {...props}
      >
        <RadioGroupPrimitive.Indicator className="size-2 rounded-full bg-primary" />
      </RadioGroupPrimitive.Item>
      {children}
    </label>
  );
}
