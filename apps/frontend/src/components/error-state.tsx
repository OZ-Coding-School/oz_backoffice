import { RotateCw, TriangleAlert } from "lucide-react";

import { cn } from "@/lib/utils";

import { Button } from "./ui/button";

/** 공통 오류 상태: 불러오기에 실패했을 때 안내와 다시 시도 버튼 (decisions F27). */
export function ErrorState({
  title = "불러오지 못했어요",
  description = "잠시 후 다시 시도해 주세요.",
  onRetry,
  className,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <section
      role="alert"
      className={cn(
        "flex flex-col items-center gap-3 rounded-xl border border-border bg-card px-6 py-10 text-center",
        className,
      )}
    >
      <span aria-hidden className="inline-flex size-12 items-center justify-center rounded-full bg-destructive-subtle">
        <TriangleAlert className="size-6 text-destructive-text" />
      </span>
      <h2 className="text-h3 text-foreground">{title}</h2>
      <p className="text-body-sm text-muted-foreground">{description}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw />
          다시 시도
        </Button>
      ) : null}
    </section>
  );
}
