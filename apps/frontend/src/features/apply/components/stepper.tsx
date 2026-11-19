import { Check, User } from "lucide-react";

import { cn } from "@/lib/utils";

import { STEPS, type FormStep } from "../steps";

/**
 * 단계 표시 (Figma Stepper). 데스크톱·태블릿은 한 줄,
 * 모바일은 첫 줄에 '1:1 멘토링', 그 아래 줄에 단계 4개 (F30, 사용자 요청).
 */
export function Stepper({ current }: { current: FormStep }) {
  const index = STEPS.findIndex((s) => s.value === current);
  return (
    <div className="flex flex-col items-start gap-2.5 md:flex-row md:items-center md:gap-2">
      <span className="inline-flex items-center gap-1 rounded-full bg-accent px-2.5 py-1 text-caption-strong text-accent-foreground">
        <User aria-hidden className="size-3.5" />
        1:1 멘토링
      </span>
      <ol
        aria-label="신청 단계"
        className="flex w-full items-center justify-between gap-2.5 md:w-auto md:justify-start"
      >
        {STEPS.map((step, i) => {
          const done = i < index;
          const active = i === index;
          return (
            <li
              key={step.value}
              className="flex items-center gap-1.5 md:gap-2"
              aria-current={active ? "step" : undefined}
            >
              {i > 0 ? <span aria-hidden className="hidden h-px w-7 bg-border md:block" /> : null}
              <span
                aria-hidden
                className={cn(
                  "inline-flex size-5.5 items-center justify-center rounded-full text-caption-strong",
                  done || active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
                )}
              >
                {done ? <Check className="size-3" /> : i + 1}
              </span>
              <span
                className={cn("text-body-sm", active ? "text-body-strong text-foreground" : "text-muted-foreground")}
              >
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
