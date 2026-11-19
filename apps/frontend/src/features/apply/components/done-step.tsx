import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { CircleCheck } from "lucide-react";

import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { formatKst, formatKstDay, formatMinutes } from "@/lib/datetime";
import { requestQuery } from "@/features/requests/api";

/** 신청 완료 (Figma `Screen / 1:1 완료`·`팀 완료`). [내 신청 보기]는 방금 만든 신청 상세(F30) */
export function DoneStep({ requestId }: { requestId: string }) {
  const request = useQuery(requestQuery(requestId));
  if (request.isPending) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }
  if (request.isError) return <ErrorState onRetry={() => void request.refetch()} />;
  const r = request.data;
  const first = r.desired_times[0];
  return (
    <section className="mx-auto flex w-full max-w-120 flex-col items-center gap-4 py-8 text-center">
      <span aria-hidden className="inline-flex size-16 items-center justify-center rounded-full bg-success-subtle">
        <CircleCheck className="size-7 text-success-text" />
      </span>
      <h1 className="text-h1 text-foreground">신청했어요</h1>
      <p className="text-body text-muted-foreground">
        {r.mentor_display_name}가 희망 일시 중 하나로 승인하면 세션이 만들어지고 채팅으로 알려 드려요.
      </p>
      <dl className="flex w-full flex-col gap-2.5 rounded-xl border border-border bg-card p-5 text-left">
        <Item label="멘토" value={`${r.mentor_display_name} · ${r.team_id ? "팀 멘토링" : "1:1 멘토링"}`} />
        <Item label="주제" value={r.topic} />
        <Item
          label="희망 일시"
          value={
            first
              ? `${formatKstDay(first)} ${formatKst(first, "HH:mm")}${r.desired_times.length > 1 ? ` 외 ${r.desired_times.length - 1}개` : ""}`
              : "-"
          }
        />
        <Item label="상태" value="멘토 승인 대기" />
        <Item
          label="차감 예정"
          value={`${formatMinutes(r.duration)} · ${r.team_id ? "팀 계좌" : "내 계좌"} (승인되면 차감)`}
        />
      </dl>
      <div className="flex gap-2">
        <Button variant="outline" asChild>
          <Link to="/">홈으로</Link>
        </Button>
        <Button asChild>
          <Link to="/mentoring/requests/$requestId" params={{ requestId: r.id }}>
            내 신청 보기
          </Link>
        </Button>
      </div>
    </section>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-4">
      <dt className="w-18 shrink-0 text-body-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-body text-foreground">{value}</dd>
    </div>
  );
}
