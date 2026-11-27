import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Plus, Users, Wallet } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { MetaChip, PageHeader } from "@/components/page-header";
import { Alert } from "@/components/ui/alert";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Spinner } from "@/components/ui/spinner";
import { cohortSettingsQuery } from "@/features/admin-academy/api";
import { hasPermissionIn, staffAccessQuery } from "@/features/staff/api";
import { formatMinutes } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { teamsQuery, unassignedQuery, type AdminTeam } from "../teams-api";
import { CreateTeamSheet } from "./create-team-sheet";
import { GrantTeamsSheet } from "./grant-teams-sheet";

const COLUMNS =
  "grid grid-cols-[40px_minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1.3fr)_120px_88px_96px] items-center gap-3";

/** 팀 관리 (F93·A39·A108): 표 · [팀 만들기] 패널 · 체크 → 떠오르는 막대 → 시간 지급 패널 */
export function TeamsPage({ cohortId }: { cohortId: string }) {
  const access = useQuery(staffAccessQuery);
  const teams = useQuery(teamsQuery(cohortId));
  const settings = useQuery(cohortSettingsQuery(cohortId));
  const unassigned = useQuery(unassignedQuery(cohortId));
  const cohort = access.data?.cohorts.find((c) => c.id === cohortId);
  const can = (code: string) => !!access.data && !!cohort && hasPermissionIn(access.data, code, cohort);
  const canManage = can("mentoring.team.manage");
  const canGrant = can("mentoring.balance.manage");
  const [creating, setCreating] = useState(false);
  const [grant, setGrant] = useState<{ teams: AdminTeam[] | null } | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const title = cohort ? `${cohort.bootcamp_name} ${cohort.cohort_number}기` : "";
  const items = teams.data ?? [];
  const memberCount = items.reduce((n, t) => n + t.members.length, 0);
  const teamAllowed = settings.data?.allow_team_mentoring ?? false;
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  return (
    <div className={cn("flex flex-col gap-6", picked.length > 0 && "pb-4")}>
      <PageHeader
        icon={Users}
        title="팀 관리"
        meta={
          <>
            <MetaChip>{title}</MetaChip>
            {teams.data ? (
              <span>
                팀 {items.length}개 · 팀원 {memberCount}명
              </span>
            ) : null}
          </>
        }
        actions={
          teamAllowed ? (
            <>
              {canGrant && items.length > 0 ? (
                <Button variant="outline" onClick={() => setGrant({ teams: null })}>
                  <Wallet aria-hidden />
                  전체 팀 지급
                </Button>
              ) : null}
              {canManage ? (
                <Button onClick={() => setCreating(true)}>
                  <Plus aria-hidden />팀 만들기
                </Button>
              ) : null}
            </>
          ) : null
        }
      />

      {teams.isPending || settings.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : teams.isError ? (
        <ErrorState onRetry={() => void teams.refetch()} />
      ) : !teamAllowed && items.length === 0 ? (
        <EmptyState
          icon={Users}
          title="이 기수는 팀 멘토링을 받지 않아요"
          description={
            <Link
              to="/admin/cohorts/$cohortId/mentoring/settings"
              params={{ cohortId }}
              className="text-primary-text hover:underline"
            >
              멘토링 설정에서 팀 멘토링을 켜면 팀을 만들 수 있어요
            </Link>
          }
        />
      ) : (
        <>
          {(unassigned.data?.length ?? 0) > 0 ? (
            <Alert
              title={`팀이 없는 수강 중 수강생 ${unassigned.data?.length}명`}
              description="팀을 만들거나 기존 팀에 넣어 주세요. 1:1 멘토링은 팀과 상관없이 신청할 수 있어요."
            />
          ) : null}
          {items.length === 0 ? (
            <EmptyState icon={Users} title="아직 팀이 없어요" description="[팀 만들기]로 첫 팀을 만들어요." />
          ) : (
            <TeamTable teams={items} picked={picked} selectable={canGrant} onToggle={toggle} onAll={setPicked} />
          )}
        </>
      )}

      {picked.length > 0 ? (
        <div className="sticky bottom-4 z-10">
          <div className="flex items-center gap-3 rounded-2xl border border-primary/40 bg-card/95 px-5 py-3 shadow-lg backdrop-blur">
            <span aria-hidden className="size-2 rounded-full bg-primary" />
            <span className="flex-1 text-body text-foreground">{picked.length}팀 선택</span>
            <Button variant="ghost" onClick={() => setPicked([])}>
              선택 해제
            </Button>
            <Button onClick={() => setGrant({ teams: items.filter((t) => picked.includes(t.id)) })}>
              <Wallet aria-hidden />
              시간 지급
            </Button>
          </div>
        </div>
      ) : null}

      {creating ? <CreateTeamSheet cohortId={cohortId} cohortTitle={title} onClose={() => setCreating(false)} /> : null}
      {grant ? (
        <GrantTeamsSheet
          cohortId={cohortId}
          cohortTitle={title}
          teams={grant.teams}
          allCount={items.length}
          defaultMinutes={settings.data?.default_team_minutes ?? 0}
          onClose={(done) => {
            setGrant(null);
            if (done) setPicked([]);
          }}
        />
      ) : null}
    </div>
  );
}

function TeamTable({
  teams,
  picked,
  selectable,
  onToggle,
  onAll,
}: {
  teams: AdminTeam[];
  picked: string[];
  selectable: boolean;
  onToggle: (id: string) => void;
  onAll: (ids: string[]) => void;
}) {
  const all = teams.length > 0 && picked.length === teams.length;
  return (
    <div
      role="table"
      aria-label="팀 목록"
      className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm"
    >
      <div
        role="row"
        className={cn(COLUMNS, "border-b border-border bg-muted px-4 py-2.5 text-caption text-muted-foreground")}
      >
        <span role="columnheader">
          {selectable ? (
            <Checkbox
              aria-label="모든 팀 고르기"
              checked={all ? true : picked.length > 0 ? "indeterminate" : false}
              onCheckedChange={() => onAll(all ? [] : teams.map((t) => t.id))}
            />
          ) : null}
        </span>
        <span role="columnheader">팀</span>
        <span role="columnheader">담당 멘토</span>
        <span role="columnheader">팀원</span>
        <span role="columnheader" className="text-right">
          팀 계좌 잔여
        </span>
        <span role="columnheader" className="text-right">
          대기 신청
        </span>
        <span role="columnheader" className="text-right">
          세션 예정·완료
        </span>
      </div>
      {teams.map((t) => {
        const on = picked.includes(t.id);
        return (
          <div
            key={t.id}
            role="row"
            aria-label={t.label}
            className={cn(COLUMNS, "border-b border-border px-4 py-3 last:border-b-0", on && "bg-sidebar-accent/40")}
          >
            <span role="cell">
              {selectable ? (
                <Checkbox aria-label={`${t.label} 고르기`} checked={on} onCheckedChange={() => onToggle(t.id)} />
              ) : null}
            </span>
            <span role="cell" className="flex min-w-0 flex-col">
              <span className="truncate text-body-strong text-foreground">{t.label}</span>
              <span className="text-caption text-muted-foreground">팀원 {t.members.length}명</span>
            </span>
            <span role="cell" className="flex min-w-0 flex-col">
              <span className="truncate text-body text-foreground">{t.mentor.display_name}</span>
              {t.mentor.name !== t.mentor.display_name ? (
                <span className="truncate text-caption text-muted-foreground">{t.mentor.name}</span>
              ) : null}
            </span>
            <span role="cell" className="flex min-w-0 items-center gap-1">
              {t.members.slice(0, 4).map((m) => (
                <span key={m.student_id} title={m.name}>
                  <Avatar name={m.name} size="sm" />
                </span>
              ))}
              {t.members.length > 4 ? (
                <span className="text-caption text-muted-foreground">+{t.members.length - 4}</span>
              ) : null}
              {t.members.length === 0 ? <span className="text-caption text-muted-foreground">없음</span> : null}
            </span>
            <span role="cell" className="text-right">
              {t.account ? (
                <span className="inline-flex items-center gap-1.5">
                  {t.account.is_expired ? <Badge variant="outline">만료</Badge> : null}
                  <span className="text-body-strong text-foreground">{formatMinutes(t.account.remaining_minutes)}</span>
                </span>
              ) : (
                <span className="text-body text-muted-foreground">지급 전</span>
              )}
            </span>
            <span role="cell" className="text-right text-body text-foreground">
              {t.pending_request_count}건
            </span>
            <span role="cell" className="text-right text-body text-foreground">
              {t.upcoming_session_count} · {t.completed_session_count}
            </span>
          </div>
        );
      })}
    </div>
  );
}
