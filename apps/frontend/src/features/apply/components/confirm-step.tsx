import { formatMinutes } from "@/lib/datetime";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { slotLabel } from "@/features/requests/labels";

import { Alert } from "@/components/ui/alert";

import type { MentorCard } from "../api";
import type { ApplyKind } from "../gate";
import type { FormStep } from "../steps";
import { MentorAvatar } from "./mentor-step";

/** ④ 신청 확인 (Figma `Screen / 1:1 신청 확인`, A42·A53·M26). 화면 문구는 '차감 예정'(F14) */
export function ConfirmStep({
  kind,
  teamLabel,
  mentor,
  duration,
  desiredTimes,
  topic,
  detail,
  remaining,
  leadHours,
  onEdit,
  submitting,
  onSubmit,
  error,
}: {
  kind: ApplyKind;
  teamLabel: string | undefined;
  mentor: MentorCard | undefined;
  duration: number;
  desiredTimes: string[];
  topic: string;
  detail: string;
  remaining: number;
  leadHours: number | undefined;
  onEdit: (step: FormStep) => void;
  submitting: boolean;
  onSubmit: () => void;
  error: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:gap-5">
      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <Card title="멘토" onEdit={kind === "team" ? undefined : () => onEdit("mentor")}>
          {mentor ? (
            <div className="flex items-center gap-3">
              <MentorAvatar mentor={mentor} size="md" />
              <div className="flex min-w-0 flex-col">
                <span className="text-body-strong text-foreground">{mentor.display_name}</span>
                <span className="text-caption text-muted-foreground">
                  {kind === "team"
                    ? `${teamLabel ?? "팀"} 담당 멘토 · 팀 멘토링`
                    : `${mentor.headline ? `${mentor.headline} · ` : ""}1:1 멘토링`}
                </span>
              </div>
            </div>
          ) : null}
        </Card>
        <Card title="일정" onEdit={() => onEdit("schedule")}>
          <dl className="flex flex-col divide-y divide-border">
            <Row label="진행 시간" value={`${duration}분`} />
            {desiredTimes.map((t, i) => (
              <Row key={t} label={`${i + 1}순위`} value={slotLabel(t, duration)} />
            ))}
          </dl>
        </Card>
        <Card title="신청 내용" onEdit={() => onEdit("content")}>
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-caption text-muted-foreground">멘토링 주제</span>
              <span className="text-body-lg text-foreground">{topic}</span>
            </div>
            <div className="flex flex-col gap-1 border-t border-border pt-3">
              <span className="text-caption text-muted-foreground">신청 내용</span>
              <div className="rounded-lg border border-border px-4 py-3">
                <Markdown>{detail}</Markdown>
              </div>
            </div>
          </div>
        </Card>
      </div>
      <aside className="flex flex-col gap-4 lg:w-85 lg:shrink-0">
        <section className="flex flex-col gap-2.5 rounded-2xl border border-border bg-card shadow-sm p-5">
          <h2 className="text-body-strong text-foreground">
            {kind === "team" ? `팀 계좌 (${teamLabel ?? "팀"})` : "내 1:1 계좌"}
          </h2>
          <Line label="남은 시간" value={formatMinutes(remaining)} />
          <Line label="차감 예정" value={`− ${formatMinutes(duration)}`} />
          <Line label="신청 후 남은 시간" value={formatMinutes(Math.max(0, remaining - duration))} strong />
          <div className="mt-2 flex flex-col gap-1 border-t border-border pt-3">
            <h3 className="text-caption-strong text-foreground">언제 차감되나요?</h3>
            <ul className="flex flex-col gap-1 text-caption text-muted-foreground">
              <li>• 신청하면 {formatMinutes(duration)}이 차감 예정으로 잡혀 남은 시간에서 빠져요</li>
              <li>• 멘토가 승인하면 차감이 확정돼요</li>
              <li>• 반려되거나, 승인 전에 취소하거나, 승인되지 않은 채 희망 일시가 모두 지나면 돌려받아요</li>
              <li>• 승인 후에도 시작 {leadHours ?? ""}시간 전까지 취소하면 모두 돌려받아요</li>
              <li>• 세션이 끝난 뒤 실제 진행 시간이 짧으면 차이만큼 돌려받고, 길면 그만큼 더 차감돼요</li>
            </ul>
          </div>
        </section>
        {kind === "team" ? (
          <Alert variant="info" title="팀원 모두에게 보여요" description="신청 내용과 결과가 팀 채팅방에 안내돼요." />
        ) : null}
        {error}
        <Button className="w-full" disabled={submitting} onClick={onSubmit}>
          신청하기
        </Button>
      </aside>
    </div>
  );
}

function Card({ title, onEdit, children }: { title: string; onEdit?: () => void; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-border bg-card shadow-sm p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-body-strong text-foreground">{title}</h2>
        {onEdit ? (
          <Button variant="link" size="sm" onClick={onEdit} aria-label={`${title} 수정`}>
            수정
          </Button>
        ) : null}
      </div>
      {children}
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-4 py-2.5 first:pt-0 last:pb-0">
      <dt className="w-18 shrink-0 text-body-sm text-muted-foreground">{label}</dt>
      <dd className="text-body text-foreground">{value}</dd>
    </div>
  );
}

function Line({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-caption text-muted-foreground">{label}</span>
      <span className={strong ? "text-body-strong text-foreground" : "text-body text-foreground"}>{value}</span>
    </div>
  );
}
