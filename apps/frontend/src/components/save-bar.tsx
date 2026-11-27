import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * 떠오르는 저장 막대 (F91): 바뀐 것이 있을 때 화면 아래에 상태 · [되돌리기] · [저장].
 * 폼 밖에 둘 때는 `form`으로 제출할 폼 id를 준다.
 */
export function SaveBar({
  dirty,
  message,
  canSave,
  pending,
  onReset,
  form,
  submitLabel = "저장",
}: {
  dirty: boolean;
  message?: string;
  canSave: boolean;
  pending: boolean;
  onReset?: () => void;
  form?: string;
  submitLabel?: string;
}) {
  return (
    <div className="sticky bottom-4 z-10">
      <div
        className={cn(
          "flex items-center gap-3 rounded-2xl border bg-card/95 px-5 py-3 shadow-lg backdrop-blur",
          dirty ? "border-primary/40" : "border-info/40",
        )}
      >
        <span aria-hidden className={cn("size-2 rounded-full", dirty ? "bg-warning" : "bg-info")} />
        <span className="flex-1 text-body text-foreground">{message ?? "저장하지 않은 변경이 있어요"}</span>
        {dirty && onReset ? (
          <Button type="button" variant="ghost" onClick={onReset} disabled={pending}>
            되돌리기
          </Button>
        ) : null}
        <Button type="submit" form={form} disabled={!canSave}>
          {submitLabel}
        </Button>
      </div>
    </div>
  );
}
