import { Link } from "@tanstack/react-router";
import { ChevronRight, CircleX, Info, User, Users } from "lucide-react";

import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { formatKst, formatKstDay } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import type { MentoringRequest } from "../api";
import { balanceLine, canceledTail, kindLabel, sessionLabel, slotLabel, STATUS_STYLE } from "../labels";

/**
 * 신청 카드 (Figma `Screen / 신청 내역`, F29).
 * 데스크톱·태블릿은 왼쪽에 신청 일시·차감 상태, 모바일은 위쪽 띠로 올린다.
 */
export function RequestCard({ request, mine }: { request: MentoringRequest; mine: boolean }) {
  const style = STATUS_STYLE[request.status];
  const balance = balanceLine(request);
  const KindIcon = request.team_id ? Users : User;
  return (
    <Link
      to="/mentoring/requests/$requestId"
      params={{ requestId: request.id }}
      aria-label={`${request.topic} · ${style.label}`}
      className={cn(
        "flex overflow-hidden rounded-xl border border-border outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
        style.card,
      )}
    >
      <span aria-hidden className={cn("w-1 shrink-0", style.bar)} />
      <div className="flex min-w-0 flex-1 flex-col md:flex-row">
        <div className="flex items-center gap-1.5 border-b border-border/60 px-4 py-2.5 md:w-35 md:shrink-0 md:flex-col md:items-start md:gap-1 md:border-r md:border-b-0 md:px-5 md:py-5 lg:w-46">
          {request.created_at ? (
            <>
              <span className="text-caption text-muted-foreground">신청</span>
              <span className="text-body-strong text-foreground">{formatKstDay(request.created_at)}</span>
              <span className="font-mono text-body-sm text-foreground">{formatKst(request.created_at, "HH:mm")}</span>
            </>
          ) : null}
          {balance ? <span className="ml-auto text-caption text-muted-foreground md:ml-0">{balance}</span> : null}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-2.5 px-4 pt-3.5 pb-4 md:px-5 md:py-4.5">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 text-caption text-muted-foreground">
              <KindIcon aria-hidden className="size-3.5" />
              {kindLabel(request)}
            </span>
            <Badge variant={style.badge} className="ml-auto">
              {style.label}
            </Badge>
          </div>
          <h2 className="text-h3 text-foreground">{request.topic}</h2>
          <Row label="멘토">
            <span className="flex min-w-0 items-center gap-2">
              <Avatar name={request.mentor_display_name} size="sm" />
              <span className="text-body-strong text-foreground">{request.mentor_display_name}</span>
              {request.mentor_headline ? (
                <span className="truncate text-caption text-muted-foreground">{request.mentor_headline}</span>
              ) : null}
            </span>
          </Row>
          {request.status === "APPROVED" && request.session ? (
            <Row label="확정 일시">
              <span className="text-body text-foreground">{sessionLabel(request.session)}</span>
            </Row>
          ) : (
            <Row label="희망 일시">
              <ul className="flex flex-col gap-0.5">
                {request.desired_times.map((t, i) => (
                  <li key={t} className="text-body text-foreground">
                    {request.desired_times.length > 1 ? `${i + 1}순위 ` : ""}
                    {slotLabel(t, request.duration)}
                  </li>
                ))}
              </ul>
            </Row>
          )}
          <Row label="신청자">
            <span className="inline-flex items-center gap-1 rounded-full border border-border bg-background py-0.5 pr-2 pl-1">
              <Avatar name={request.requester_name} size="sm" className="size-5" />
              <span className="text-caption text-foreground">
                {request.requester_name}
                {mine ? " (나)" : ""}
              </span>
            </span>
          </Row>
          <StatusNote request={request} mine={mine} />
        </div>
        <span aria-hidden className="hidden items-center pr-4 text-muted-foreground md:flex">
          <ChevronRight className="size-4.5" />
        </span>
      </div>
    </Link>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 items-start gap-2">
      <span className="w-14 shrink-0 pt-0.5 text-caption text-muted-foreground">{label}</span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

/** 승인 안내 · 반려 사유 · 취소 사유 상자 */
export function StatusNote({ request, mine }: { request: MentoringRequest; mine: boolean }) {
  if (request.status === "APPROVED") {
    return <Note tone="success" icon={Info} text="승인됐어요. 진행 기록에서 세션을 확인하세요" />;
  }
  if (request.status === "REJECTED" && request.reject_reason) {
    return <Note tone="destructive" icon={CircleX} text={`반려 사유 · ${request.reject_reason}`} />;
  }
  if (request.status === "CANCELED" && request.cancel_reason) {
    const tail = canceledTail(request, mine);
    return <Note tone="warning" icon={Info} text={`취소 사유 · ${request.cancel_reason}${tail ? ` (${tail})` : ""}`} />;
  }
  return null;
}

const NOTE_TONE = {
  success: "bg-success/15",
  destructive: "bg-destructive/15",
  warning: "bg-warning/20",
} as const;

function Note({ tone, icon: Icon, text }: { tone: keyof typeof NOTE_TONE; icon: typeof Info; text: string }) {
  return (
    <p className={cn("flex items-start gap-2 rounded-md px-3 py-2 text-body-sm text-foreground", NOTE_TONE[tone])}>
      <Icon aria-hidden className="mt-0.5 size-3.5 shrink-0" />
      <span className="min-w-0">{text}</span>
    </p>
  );
}
