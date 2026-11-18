import type { LucideIcon } from "lucide-react";
import { Label } from "radix-ui";
import { useId, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Figma `Input`의 라벨·도움말·오류 묶음. 입력 요소는 render prop으로 받아 id·aria 속성을 연결한다.
 * 오류가 있으면 도움말 대신 오류 문구(destructive-text)를 보여 준다.
 */
export function FormField({
  label,
  helper,
  error,
  className,
  children,
}: {
  label: ReactNode;
  helper?: ReactNode;
  error?: string | undefined;
  className?: string;
  children: (props: { id: string; "aria-invalid"?: true; "aria-describedby"?: string }) => ReactNode;
}) {
  const id = useId();
  const messageId = `${id}-message`;
  const message = error ?? helper;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <Label.Root htmlFor={id} className="text-label text-foreground">
        {label}
      </Label.Root>
      {children({
        id,
        ...(error ? { "aria-invalid": true as const } : {}),
        ...(message ? { "aria-describedby": messageId } : {}),
      })}
      {message ? (
        <p id={messageId} className={cn("text-caption", error ? "text-destructive-text" : "text-muted-foreground")}>
          {message}
        </p>
      ) : null}
    </div>
  );
}

/** 입력 칸 왼쪽 아이콘 (Figma Input의 Leading icon). 입력 칸에는 `pl-9`를 준다. */
export function InputIcon({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <Icon
      aria-hidden
      className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
    />
  );
}
