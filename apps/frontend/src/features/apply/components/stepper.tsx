import { Check, User, Users } from "lucide-react";

import { cn } from "@/lib/utils";

import type { ApplyKind } from "../gate";
import { STEPS, type FormStep } from "../steps";

/**
 * 단계 표시 (Figma Stepper). 데스크톱·태블릿은 한 줄,
 * 모바일은 첫 줄에 종류('1:1 멘토링'·'팀 멘토링'), 그 아래 줄에 단계 (F30, 사용자 요청).
 * 종류 선택 화면(kind 없음)은 종류까지 5단계이고 모바일에서 줄을 바꾼다 (F31).
 */
export function Stepper({ kind, current }: { kind: ApplyKind | null; current: FormStep | "kind" }) {
  const steps = kind
    ? STEPS.map((s) => (s.value === "mentor" && kind === "team" ? { ...s, label: "멘토 확인" } : s))
    : [
        { value: "kind" as const, label: "멘토링 종류" },
        { value: "mentor" as const, label: "멘토" },
        ...STEPS.slice(1),
      ];
  const index = steps.findIndex((s) => s.value === current);
  const KindIcon = kind === "team" ? Users : User;
  return (
    <div className="flex flex-col items-start gap-2.5 md:flex-row md:items-center md:gap-2">
      {kind ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-accent px-2.5 py-1 text-caption-strong text-accent-foreground">
          <KindIcon aria-hidden className="size-3.5" />
          {kind === "team" ? "팀 멘토링" : "1:1 멘토링"}
        </span>
      ) : null}
      <ol
        aria-label="신청 단계"
        className={cn(
          "flex w-full items-center gap-x-3 gap-y-2 md:w-auto md:justify-start md:gap-2",
          kind ? "justify-between gap-x-1.5" : "flex-wrap",
        )}
      >
        {steps.map((step, i) => {
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
                className={cn(
                  "whitespace-nowrap",
                  active ? "text-label text-foreground md:text-body-strong" : "text-body-sm text-muted-foreground",
                )}
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
