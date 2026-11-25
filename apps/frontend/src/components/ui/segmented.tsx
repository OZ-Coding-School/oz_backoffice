import { RadioGroup as RadioGroupPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";

/**
 * 세그먼트 버튼 (F85): 두세 개 중 하나를 고르는 입력. 회색 바탕 안에서 고른 칸만
 * 메뉴 선택 항목과 같은 파스텔(사이드바 강조색) 바탕 + 굵은 글자 + 연한 테두리로 띄운다.
 * 접근성은 라디오 그룹(방향키로 이동).
 */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  id,
  disabled,
  className,
}: {
  value: T;
  onChange: (value: T) => void;
  options: readonly { value: T; label: string }[];
  /** 그룹의 접근성 이름 */
  label: string;
  id?: string;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <RadioGroupPrimitive.Root
      id={id}
      value={value}
      onValueChange={(v) => onChange(v as T)}
      aria-label={label}
      disabled={disabled}
      orientation="horizontal"
      className={cn("flex w-full gap-0.5 rounded-md bg-muted p-0.5", className)}
    >
      {options.map((o) => (
        <RadioGroupPrimitive.Item
          key={o.value}
          value={o.value}
          className={cn(
            "flex h-8 flex-1 items-center justify-center rounded-sm border border-transparent px-3 text-body text-muted-foreground outline-none transition-colors",
            "hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
            "data-[state=checked]:border-primary/50 data-[state=checked]:bg-sidebar-accent data-[state=checked]:text-body-strong data-[state=checked]:text-sidebar-accent-foreground",
          )}
        >
          {o.label}
        </RadioGroupPrimitive.Item>
      ))}
    </RadioGroupPrimitive.Root>
  );
}
