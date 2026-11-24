import { X } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import { cn } from "@/lib/utils";

import { addChip } from "../form";

/**
 * 전문 분야 칩 입력 (Figma `Expertise`, F56). Enter·쉼표로 넣고, 빈 칸에서 Backspace로 마지막 칩을 지운다.
 * 칸을 벗어나면 적던 글도 칩으로 넣는다
 */
export function ExpertiseInput({
  id,
  value,
  onChange,
  invalid,
  describedBy,
}: {
  id: string;
  value: string[];
  onChange: (next: string[]) => void;
  invalid?: boolean;
  describedBy?: string;
}) {
  const [draft, setDraft] = useState("");
  const commit = () => {
    if (!draft.trim()) return;
    onChange(addChip(value, draft));
    setDraft("");
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.nativeEvent.isComposing) return; // 한글 조합 중 Enter는 조합 끝내기
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commit();
    } else if (e.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  };
  return (
    <div
      className={cn(
        "flex min-h-10 flex-wrap items-center gap-1.5 rounded-md border border-input bg-background px-2 py-1.5",
        "focus-within:border-ring focus-within:ring-1 focus-within:ring-ring",
        invalid && "border-destructive",
      )}
    >
      {value.map((chip) => (
        <span
          key={chip}
          className="inline-flex items-center gap-1 rounded-full bg-secondary py-0.5 pr-1 pl-2.5 text-caption text-secondary-foreground"
        >
          {chip}
          <button
            type="button"
            aria-label={`${chip} 빼기`}
            onClick={() => onChange(value.filter((c) => c !== chip))}
            className="inline-flex size-4 items-center justify-center rounded-full outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X aria-hidden className="size-3" />
          </button>
        </span>
      ))}
      <input
        id={id}
        value={draft}
        onChange={(e) => setDraft(e.target.value.replace(",", ""))}
        onKeyDown={onKeyDown}
        onBlur={commit}
        placeholder={value.length ? "" : "입력 후 Enter"}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        className="min-w-24 flex-1 bg-transparent px-1 text-body text-foreground outline-none placeholder:text-muted-foreground"
      />
    </div>
  );
}
