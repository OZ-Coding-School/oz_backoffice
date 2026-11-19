import { ChevronLeft, ChevronRight } from "lucide-react";
import type { ComponentProps } from "react";
import { DayPicker } from "react-day-picker";
import { ko } from "react-day-picker/locale";

import { TIME_ZONE } from "@/lib/datetime";
import { cn } from "@/lib/utils";

/**
 * Figma `Components / Calendar` (shadcn Calendar 구조, react-day-picker, F30).
 * 한국어·Asia/Seoul. 일요일은 붉은 글자, 오늘은 accent, 고른 날은 primary.
 * `modifiers.available`이 있는 날은 아래에 점을 찍는다.
 */
export function Calendar({ className, classNames, modifiersClassNames, ...props }: ComponentProps<typeof DayPicker>) {
  return (
    <DayPicker
      locale={ko}
      timeZone={TIME_ZONE}
      showOutsideDays
      className={cn("rounded-lg border border-border bg-card p-3", className)}
      classNames={{
        months: "relative flex flex-col",
        month: "flex flex-col gap-3",
        month_caption: "flex h-8 items-center justify-center",
        caption_label: "text-body-strong text-foreground",
        nav: "absolute inset-x-0 top-0 flex h-8 items-center justify-between",
        button_previous:
          "inline-flex size-8 items-center justify-center rounded-md text-foreground hover:bg-accent disabled:opacity-40",
        button_next:
          "inline-flex size-8 items-center justify-center rounded-md text-foreground hover:bg-accent disabled:opacity-40",
        month_grid: "w-full border-collapse",
        weekdays: "flex",
        weekday: "flex-1 pb-1 text-center text-caption text-muted-foreground first:text-destructive-text",
        week: "mt-1 flex w-full",
        day: "relative flex-1 p-0 text-center",
        day_button: cn(
          "mx-auto inline-flex size-9 items-center justify-center rounded-md text-body text-foreground outline-none",
          "hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none",
        ),
        today: "[&>button]:bg-accent [&>button]:text-accent-foreground",
        selected: "[&>button]:bg-primary! [&>button]:text-primary-foreground!",
        outside: "[&>button]:text-muted-foreground/50",
        disabled: "[&>button]:text-muted-foreground/50",
        hidden: "invisible",
        ...classNames,
      }}
      modifiersClassNames={{
        available:
          "after:absolute after:bottom-0.5 after:left-1/2 after:size-1 after:-translate-x-1/2 after:rounded-full after:bg-primary",
        ...modifiersClassNames,
      }}
      components={{ Chevron }}
      {...props}
    />
  );
}

function Chevron({ orientation }: { orientation?: "up" | "down" | "left" | "right" }) {
  return orientation === "left" ? (
    <ChevronLeft aria-hidden className="size-4" />
  ) : (
    <ChevronRight aria-hidden className="size-4" />
  );
}
