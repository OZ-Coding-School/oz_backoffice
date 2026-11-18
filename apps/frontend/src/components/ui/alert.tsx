import { cva, type VariantProps } from "class-variance-authority";
import { CircleAlert, CircleCheck, CircleX, Info, TriangleAlert } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Figma `Components / Alert` (Info·Success·Warning·Error). 제목은 상태 글자 색, 설명은 기본 글자 색. */
const alertVariants = cva("flex w-full gap-3 rounded-lg border px-4 py-3 text-left", {
  variants: {
    variant: {
      info: "border-info-text bg-info-subtle [--alert-accent:var(--info-text)]",
      success: "border-success-text bg-success-subtle [--alert-accent:var(--success-text)]",
      warning: "border-warning-text bg-warning-subtle [--alert-accent:var(--warning-text)]",
      error: "border-destructive-text bg-destructive-subtle [--alert-accent:var(--destructive-text)]",
    },
  },
  defaultVariants: { variant: "info" },
});

const ICONS = { info: Info, success: CircleCheck, warning: TriangleAlert, error: CircleX } as const;

export type AlertProps = Omit<ComponentProps<"div">, "title"> &
  VariantProps<typeof alertVariants> & { title: ReactNode; description?: ReactNode };

export function Alert({ className, variant, title, description, ...props }: AlertProps) {
  const Icon = ICONS[variant ?? "info"] ?? CircleAlert;
  return (
    <div
      data-slot="alert"
      role={variant === "error" || variant === "warning" ? "alert" : "status"}
      className={cn(alertVariants({ variant }), className)}
      {...props}
    >
      <Icon aria-hidden className="mt-0.5 size-4 shrink-0 text-(--alert-accent)" />
      <div className="flex min-w-0 flex-col gap-0.5">
        <p className="text-body-strong text-(--alert-accent)">{title}</p>
        {description ? <div className="text-body-sm text-foreground">{description}</div> : null}
      </div>
    </div>
  );
}
