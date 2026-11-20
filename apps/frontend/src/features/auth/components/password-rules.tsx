import { CircleCheck, CircleX } from "lucide-react";

import { cn } from "@/lib/utils";

import { PASSWORD_RULES } from "../password";

/** 비밀번호 규칙 충족 표시 (A30·F37): 입력하는 대로 규칙마다 충족 여부를 보여 준다 */
export function PasswordRules({ value }: { value: string }) {
  return (
    <ul aria-label="비밀번호 규칙" className="flex flex-col gap-1 rounded-lg bg-muted px-3 py-2.5">
      {PASSWORD_RULES.map((rule) => {
        const ok = rule.test(value);
        const Icon = ok ? CircleCheck : CircleX;
        return (
          <li
            key={rule.id}
            className={cn("flex items-center gap-2 text-caption", ok ? "text-success-text" : "text-muted-foreground")}
          >
            <Icon aria-hidden className="size-4" />
            {rule.label}
            <span className="sr-only">{ok ? " (충족)" : " (미충족)"}</span>
          </li>
        );
      })}
    </ul>
  );
}
