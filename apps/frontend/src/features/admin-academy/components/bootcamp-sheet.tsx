import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useId, useState } from "react";
import { toast } from "sonner";

import { PanelActions, PanelHead, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { teamsQuery, type Team } from "@/features/admin-org/api";
import { DiscardDialog } from "@/features/admin-org/components/shared";
import { errorText } from "@/features/admin-org/text";
import { hasPermission, type StaffAccess } from "@/features/staff/api";

import { useSaveBootcamp, type Bootcamp } from "../api";

const NO_TEAM = "none";
const ALIAS_MAX = 50;
const ALIAS_HELP =
  "Airtable 수강생 명단의 '기수' 값 앞부분(예: '헬스케어 3기'의 '헬스케어')이에요. 비우면 이 과정은 명단 동기화에서 빠져요.";
const TEAM_HELP = "이 과정을 맡는 팀이에요. 조직 설정 > 부서의 팀 패널에서도 바꿀 수 있어요.";

/** 과정 패널 (F68·F74): 기본 정보(조회만)·운영(사용 여부·Airtable 별칭·담당 팀) */
export function BootcampSheet({
  bootcamp: b,
  access,
  onClose,
}: {
  bootcamp: Bootcamp;
  access: StaffAccess;
  onClose: () => void;
}) {
  const canEditBootcamp = hasPermission(access, "academy.bootcamp.manage");
  const canSeeTeams = hasPermission(access, "org.department.read");
  const canEditTeam = hasPermission(access, "org.department.manage");
  const teams = useQuery({ ...teamsQuery, enabled: canSeeTeams });
  const team = teams.data?.find((t) => t.bootcamp_ids.includes(b.id)) ?? null;
  const [editing, setEditing] = useState(false);
  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined}>
        <PanelHead
          title={b.name}
          description={`과정 · ${b.code}`}
          badges={
            editing ? (
              <Badge variant="info">수정 중</Badge>
            ) : (
              <Badge variant={b.is_active ? "success" : "secondary"}>{b.is_active ? "사용 중" : "사용 안 함"}</Badge>
            )
          }
          actions={
            (canEditBootcamp || canEditTeam) && !editing ? <PanelActions onEdit={() => setEditing(true)} /> : null
          }
          onClose={onClose}
        />
        {editing ? (
          <BootcampForm
            bootcamp={b}
            team={team}
            teams={canSeeTeams ? (teams.data ?? []) : null}
            canEditBootcamp={canEditBootcamp}
            canEditTeam={canEditTeam && canSeeTeams}
            onDone={() => setEditing(false)}
          />
        ) : (
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
            <BasicSection bootcamp={b} />
            <PanelSection title="운영">
              <PanelRow label="사용 여부">{b.is_active ? "사용" : "사용 안 함"}</PanelRow>
              <PanelRow label="기수 별칭" help={ALIAS_HELP}>
                {b.airtable_cohort_prefix ?? "—"}
              </PanelRow>
              {canSeeTeams ? (
                <PanelRow label="담당 팀" help={TEAM_HELP}>
                  {teams.data ? (team?.name ?? "없음") : "불러오는 중…"}
                </PanelRow>
              ) : null}
            </PanelSection>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function BasicSection({ bootcamp: b }: { bootcamp: Bootcamp }) {
  return (
    <PanelSection title="기본 정보">
      <PanelRow label="이름">{b.name}</PanelRow>
      <PanelRow label="코드">{b.code}</PanelRow>
      <PanelRow label="HRD 과정">
        <span className="break-all">{[b.hrd_net_id, b.hrd_bootcamp_name].filter(Boolean).join(" · ") || "—"}</span>
      </PanelRow>
    </PanelSection>
  );
}

function BootcampForm({
  bootcamp: b,
  team,
  teams,
  canEditBootcamp,
  canEditTeam,
  onDone,
}: {
  bootcamp: Bootcamp;
  team: Team | null;
  teams: Team[] | null;
  canEditBootcamp: boolean;
  canEditTeam: boolean;
  onDone: () => void;
}) {
  const id = useId();
  const [active, setActive] = useState(b.is_active);
  const [alias, setAlias] = useState(b.airtable_cohort_prefix ?? "");
  const [teamId, setTeamId] = useState(team?.id ?? NO_TEAM);
  const [error, setError] = useState<string | null>(null);
  const save = useSaveBootcamp(b);
  const nextAlias = alias.trim() || null;
  const values: { is_active?: boolean; airtable_cohort_prefix?: string | null } = {};
  if (active !== b.is_active) values.is_active = active;
  if (nextAlias !== (b.airtable_cohort_prefix ?? null)) values.airtable_cohort_prefix = nextAlias;
  const teamChanged = teamId !== (team?.id ?? NO_TEAM);
  const dirty = Object.keys(values).length > 0 || teamChanged;
  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !save.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });
  const onSubmit = async () => {
    setError(null);
    try {
      await save.mutateAsync({
        values,
        ...(teamChanged ? { teamChange: { team_id: teamId === NO_TEAM ? null : teamId } } : {}),
      });
      toast.success(`${b.name} 과정을 저장했어요`);
      onDone();
    } catch (e) {
      setError(errorText(e));
    }
  };
  return (
    <form
      aria-label="과정 수정"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void onSubmit();
      }}
      className="flex min-h-0 flex-1 flex-col"
    >
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
        <BasicSection bootcamp={b} />
        <PanelSection title="운영">
          <PanelRow label="사용 여부" htmlFor={`${id}-active`}>
            {canEditBootcamp ? (
              <span className="flex items-center gap-2 font-normal">
                <Switch id={`${id}-active`} checked={active} onCheckedChange={setActive} />
                {active ? "사용" : "사용 안 함"}
              </span>
            ) : b.is_active ? (
              "사용"
            ) : (
              "사용 안 함"
            )}
          </PanelRow>
          <PanelRow label="기수 별칭" htmlFor={`${id}-alias`} help={ALIAS_HELP}>
            {canEditBootcamp ? (
              <Input
                id={`${id}-alias`}
                maxLength={ALIAS_MAX}
                placeholder="예: 백엔드"
                className="font-normal"
                value={alias}
                onChange={(e) => setAlias(e.target.value)}
              />
            ) : (
              (b.airtable_cohort_prefix ?? "—")
            )}
          </PanelRow>
          {teams ? (
            <PanelRow label="담당 팀" htmlFor={`${id}-team`} help={TEAM_HELP}>
              {canEditTeam ? (
                <Select value={teamId} onValueChange={setTeamId}>
                  <SelectTrigger id={`${id}-team`} className="font-normal">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_TEAM}>없음</SelectItem>
                    {teams.map((t) => (
                      <SelectItem key={t.id} value={t.id}>
                        {t.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                (team?.name ?? "없음")
              )}
            </PanelRow>
          ) : null}
        </PanelSection>
        {error ? <Alert variant="error" title={error} /> : null}
      </div>
      <div className="flex justify-end gap-2 border-t border-border px-6 py-3">
        <Button type="button" variant="outline" onClick={onDone}>
          취소
        </Button>
        <Button type="submit" disabled={save.isPending || !dirty}>
          저장
        </Button>
      </div>
      <DiscardDialog blocker={blocker} />
    </form>
  );
}
