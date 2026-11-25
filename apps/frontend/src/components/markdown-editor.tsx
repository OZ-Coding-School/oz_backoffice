import { useState } from "react";

import { Markdown } from "@/components/markdown";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

/**
 * 마크다운 편집기 (F79): '작성 | 미리보기' 탭 + 큰 입력칸.
 * 멘토 소개(멘토 내 프로필·운영진 대리 수정)에서 쓴다. 미리보기는 공용 `<Markdown>`.
 */
export function MarkdownEditor({
  id,
  value,
  onChange,
  onBlur,
  maxLength,
  invalid,
  describedBy,
  rows = 14,
  placeholder,
  label,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  maxLength?: number;
  invalid?: boolean;
  describedBy?: string;
  rows?: number;
  placeholder?: string;
  /** 탭 묶음의 접근성 이름 */
  label: string;
}) {
  const [mode, setMode] = useState<"write" | "preview">("write");
  return (
    <div className="flex flex-col gap-2">
      <div role="tablist" aria-label={label} className="flex gap-1 self-end">
        {(
          [
            ["write", "작성"],
            ["preview", "미리보기"],
          ] as const
        ).map(([key, text]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={mode === key}
            onClick={() => setMode(key)}
            className={cn(
              "-mb-px border-b-2 px-3 py-1.5 text-label outline-none focus-visible:ring-2 focus-visible:ring-ring",
              mode === key
                ? "border-primary text-primary-text"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {text}
          </button>
        ))}
      </div>
      {mode === "write" ? (
        <Textarea
          id={id}
          rows={rows}
          value={value}
          maxLength={maxLength}
          placeholder={placeholder}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          className="text-body"
        />
      ) : (
        <div
          role="tabpanel"
          aria-label="미리보기"
          className="min-h-40 rounded-md border border-border bg-background px-4 py-3"
        >
          {value.trim() ? (
            <Markdown>{value}</Markdown>
          ) : (
            <p className="text-body text-muted-foreground">미리 볼 내용이 없어요.</p>
          )}
        </div>
      )}
    </div>
  );
}
