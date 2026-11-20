import { useEffect, useEffectEvent, useRef } from "react";

/** 무한 스크롤 (F29): 목록 끝이 화면에 들어오면 다음 묶음을 불러온다 */
export function LoadMore({ loading, label, onVisible }: { loading: boolean; label: string; onVisible: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const visible = useEffectEvent(onVisible);
  // 불러온 뒤에도 끝이 보이면 다시 관찰을 시작해 바로 다음 묶음을 부른다
  useEffect(() => {
    const el = ref.current;
    if (loading || !el || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) visible();
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [loading]);
  return (
    <div ref={ref} className="flex justify-center py-2 text-body-sm text-muted-foreground">
      {loading ? label : ""}
    </div>
  );
}
