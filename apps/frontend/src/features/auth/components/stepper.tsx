import { Check } from "lucide-react";
import { Fragment } from "react";

import { cn } from "@/lib/utils";

/**
 * 가입 단계 표시 (Figma `Stepper`). 지난 단계는 체크, 현재 단계는 보라 점.
 * 모바일에서는 현재 단계 이름만 보여 준다 (decisions F24).
 */
export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol aria-label="가입 단계" className="flex items-center gap-1">
      {steps.map((label, index) => {
        const done = index < current;
        const active = index === current;
        return (
          <Fragment key={label}>
            {index > 0 ? (
              <li aria-hidden className={cn("h-px min-w-3 flex-1", done || active ? "bg-primary" : "bg-border")} />
            ) : null}
            <li aria-current={active ? "step" : undefined} className="flex shrink-0 items-center gap-1">
              <span
                className={cn(
                  "inline-flex size-5.5 items-center justify-center rounded-full text-caption-strong",
                  done || active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
                )}
              >
                {done ? <Check aria-hidden className="size-3" /> : index + 1}
              </span>
              <span
                className={cn(
                  "text-caption",
                  active ? "text-caption-strong text-foreground" : "hidden text-muted-foreground md:inline",
                )}
              >
                {label}
                {done ? <span className="sr-only"> (완료)</span> : null}
              </span>
            </li>
          </Fragment>
        );
      })}
    </ol>
  );
}
