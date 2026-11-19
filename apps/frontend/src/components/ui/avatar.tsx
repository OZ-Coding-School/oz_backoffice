import { cn } from "@/lib/utils";

/** Figma `Components / Avatar`: 이름 첫 글자를 accent 원 안에 보여 준다. sm 24 · md 32. */
export function Avatar({ name, size = "md", className }: { name: string; size?: "sm" | "md"; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground",
        size === "sm" ? "size-6 text-caption-strong" : "size-8 text-label",
        className,
      )}
    >
      {name.slice(0, 1)}
    </span>
  );
}
