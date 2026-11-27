import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * Figma `Components / Badge`. 상태는 배지로 보여 주고 텍스트에는 상태 색을 쓰지 않는다(F14).
 * 상태 색 배지는 진한 파스텔 바탕 + 같은 색 테두리로 바탕과 상태가 확실히 구분되게 한다(F97).
 */
const badgeVariants = cva(
  "inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-caption-strong [&_svg]:size-3",
  {
    variants: {
      variant: {
        default: "bg-accent text-accent-foreground ring-1 ring-inset ring-primary/20",
        primary: "bg-primary text-primary-foreground",
        violet: "bg-primary/15 text-primary-text ring-1 ring-inset ring-primary/35",
        secondary: "bg-muted-foreground/15 text-foreground ring-1 ring-inset ring-muted-foreground/25",
        outline: "border border-border text-foreground",
        dashed: "border border-dashed border-muted-foreground/60 text-muted-foreground",
        success: "bg-success/15 text-success-text ring-1 ring-inset ring-success/35",
        warning: "bg-warning/20 text-warning-text ring-1 ring-inset ring-warning/45",
        info: "bg-info/15 text-info-text ring-1 ring-inset ring-info/35",
        destructive: "bg-destructive/15 text-destructive-text ring-1 ring-inset ring-destructive/35",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export type BadgeProps = ComponentProps<"span"> & VariantProps<typeof badgeVariants>;

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}
