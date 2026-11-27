import { CircleCheck, TriangleAlert } from "lucide-react";
import { useId, useState } from "react";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { PanelHead, PanelList, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { formatMinutes } from "@/lib/datetime";

import { useGrantTeams, type AdminTeam, type GrantResult } from "../teams-api";

const REASON_MAX = 200;

const ERROR_MESSAGES: Record<string, string> = {
  invalid_balance_minutes: "지급 시간은 1시간 단위로 적어 주세요.",
  invalid_balance_validity: "사용 기간의 시작일이 종료일보다 앞이어야 해요.",
  balance_validity_outside_cohort: "사용 기간은 기수 기간 안이어야 해요.",
  invalid_balance_reason: "지급 사유를 다시 확인해 주세요.",
  mentoring_settings_not_configured: "기수 기본 지급 시간이 없어요. 시간을 적거나 멘토링 설정을 먼저 저장해 주세요.",
  grant_target_required: "지급할 팀을 하나 이상 골라 주세요.",
};

function newKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random()}`;
}

/** 팀 시간 지급 패널 (F68·F93·A39·A40): 고른 팀 또는 전체 팀, 결과는 지급·건너뜀 사유 */
export function GrantTeamsSheet({
  cohortId,
  cohortTitle,
  teams,
  allCount,
  defaultMinutes,
  onClose,
}: {
  cohortId: string;
  cohortTitle: string;
  /** null이면 전체 팀 */
  teams: AdminTeam[] | null;
  allCount: number;
  defaultMinutes: number;
  onClose: (done: boolean) => void;
}) {
  const id = useId();
  const grant = useGrantTeams(cohortId);
  const [key] = useState(newKey);
  const [hours, setHours] = useState("");
  const [from, setFrom] = useState("");
  const [until, setUntil] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GrantResult | null>(null);
  const target = teams ? `선택한 ${teams.length}팀` : `전체 ${allCount}팀`;
  const names = new Map((teams ?? []).map((t) => [t.id, t.label]));

  const submit = async () => {
    setError(null);
    const h = hours.trim();
    if (h && !/^\d{1,3}$/.test(h)) {
      setError("지급 시간은 0 이상의 시간(정수)으로 적어 주세요.");
      return;
    }
    if (!reason.trim()) {
      setError("지급 사유를 적어 주세요.");
      return;
    }
    try {
      const r = await grant.mutateAsync({
        teamIds: teams ? teams.map((t) => t.id) : null,
        minutes: h ? Number(h) * 60 : null,
        validFrom: from || null,
        validUntil: until || null,
        reason: reason.trim(),
        idempotencyKey: key,
      });
      setResult(r);
      toast.success(`${r.granted.length}팀에 시간을 지급했어요`);
    } catch (e) {
      const code = e instanceof ApiError ? e.code : undefined;
      setError((code && ERROR_MESSAGES[code]) ?? "지급하지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  };

  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose(!!result))}>
      <SheetContent aria-describedby={undefined} className="w-120">
        <PanelHead title="팀 시간 지급" description={`${cohortTitle} · ${target}`} onClose={() => onClose(!!result)} />
        {result ? (
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
            <PanelSection title="결과">
              <PanelRow label="지급">
                <span className="inline-flex items-center gap-1.5">
                  <CircleCheck aria-hidden className="size-4 text-success-text" />
                  {result.granted.length}팀
                  {result.granted[0] ? ` · 팀마다 ${formatMinutes(result.granted[0].minutes)}` : ""}
                </span>
              </PanelRow>
              <PanelRow label="건너뜀">
                <span className="inline-flex items-center gap-1.5">
                  {result.skipped.length > 0 ? (
                    <TriangleAlert aria-hidden className="size-4 text-warning-text" />
                  ) : null}
                  {result.skipped.length}팀
                </span>
              </PanelRow>
              {result.skipped.length > 0 ? (
                <PanelList
                  label="건너뛴 팀"
                  items={result.skipped.map((s) => ({
                    id: s.owner_id,
                    name: names.get(s.owner_id) ?? "팀",
                    meta: s.message,
                  }))}
                />
              ) : null}
            </PanelSection>
            <div className="flex justify-end">
              <Button onClick={() => onClose(true)}>닫기</Button>
            </div>
          </div>
        ) : (
          <form
            aria-label="팀 시간 지급"
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
            className="flex min-h-0 flex-1 flex-col"
          >
            <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
              <PanelSection title="지급">
                <PanelRow
                  label="시간"
                  htmlFor={`${id}-hours`}
                  help={`비우면 기수 기본 지급 시간(${formatMinutes(defaultMinutes)})을 줘요. 1시간 단위예요.`}
                >
                  <span className="flex items-center gap-2 font-normal">
                    <Input
                      id={`${id}-hours`}
                      inputMode="numeric"
                      placeholder={String(defaultMinutes / 60)}
                      className="w-24"
                      value={hours}
                      onChange={(e) => setHours(e.target.value)}
                    />
                    <span className="text-body text-muted-foreground">시간</span>
                  </span>
                </PanelRow>
                <PanelRow
                  label="사용 기간"
                  help="처음 지급하는 팀의 계좌에만 적용돼요. 비우면 기수 기간이에요. 이미 계좌가 있으면 기간은 그대로예요."
                >
                  <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 font-normal">
                    <Input
                      type="date"
                      aria-label="사용 시작일"
                      value={from}
                      onChange={(e) => setFrom(e.target.value)}
                    />
                    <span aria-hidden className="text-muted-foreground">
                      ~
                    </span>
                    <Input
                      type="date"
                      aria-label="사용 종료일"
                      value={until}
                      onChange={(e) => setUntil(e.target.value)}
                    />
                  </div>
                </PanelRow>
              </PanelSection>
              <PanelSection title="기타">
                <PanelRow label="사유" htmlFor={`${id}-reason`}>
                  <Input
                    id={`${id}-reason`}
                    maxLength={REASON_MAX}
                    placeholder="예: 프로젝트 기간 팀 멘토링"
                    className="font-normal"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </PanelRow>
              </PanelSection>
              {teams ? (
                <PanelSection title={`대상 · ${teams.length}팀`}>
                  <PanelList label="지급할 팀" items={teams.map((t) => ({ id: t.id, name: t.label }))} />
                </PanelSection>
              ) : null}
              {error ? <Alert variant="error" title={error} /> : null}
            </div>
            <div className="flex justify-end gap-2 border-t border-border px-6 py-3">
              <Button type="button" variant="outline" onClick={() => onClose(false)}>
                취소
              </Button>
              <Button type="submit" disabled={grant.isPending}>
                지급
              </Button>
            </div>
          </form>
        )}
      </SheetContent>
    </Sheet>
  );
}
