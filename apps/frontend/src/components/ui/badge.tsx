import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/** Figma `Components / Badge`. 상태는 배지로 보여 주고 텍스트에는 상태 색을 쓰지 않는다(F14). */
const badgeVariants = cva(
  "inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-caption-strong [&_svg]:size-3",
  {
    variants: {
      variant: {
        default: "bg-accent text-accent-foreground",
        primary: "bg-primary text-primary-foreground",
        secondary: "bg-secondary text-secondary-foreground",
        outline: "border border-border text-foreground",
        success: "bg-success-subtle text-success-text",
        warning: "bg-warning-subtle text-warning-text",
        info: "bg-info-subtle text-info-text",
        destructive: "bg-destructive-subtle text-destructive-text",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export type BadgeProps = ComponentProps<"span"> & VariantProps<typeof badgeVariants>;

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}
