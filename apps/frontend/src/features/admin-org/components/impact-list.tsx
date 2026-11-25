import { BookOpen, UserPlus, Users, UsersRound } from "lucide-react";

import { CollapsibleGroup, GroupItem } from "@/components/collapsible-group";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";

import type { OrgImpact } from "../api";

const REGISTRATION_STATUS = { PENDING: "대기", APPROVED: "승인", REJECTED: "반려" } as const;

/**
 * 영향받는 대상 (A93·F69): 종류마다 접는 상자(처음엔 접힘). 없는 종류는 그리지 않는다.
 * `registrationNote`는 신청 상자 건수 옆 보충 문구(예: '승인되면 적용').
 */
export function ImpactList({
  impact,
  registrationNote,
  pendingOnly = false,
}: {
  impact: OrgImpact | undefined;
  registrationNote?: string;
  /** 대기 중인 신청만 보인다 (권한 저장처럼 처리된 신청은 상관없을 때) */
  pendingOnly?: boolean;
}) {
  if (!impact)
    return (
      <div className="flex justify-center py-4">
        <Spinner />
      </div>
    );
  const registrations = pendingOnly ? impact.registrations.filter((r) => r.status === "PENDING") : impact.registrations;
  const teams = impact.teams ?? [];
  const bootcamps = impact.bootcamps ?? [];
  return (
    <div className="flex max-h-80 flex-col gap-2 overflow-y-auto">
      {teams.length ? (
        <CollapsibleGroup
          title="팀"
          count={`${teams.length}개`}
          leading={<UsersRound aria-hidden className="size-4" />}
        >
          {teams.map((t) => (
            <GroupItem key={t.id} main={t.name} sub={`직원 ${t.employee_count}명`} />
          ))}
        </CollapsibleGroup>
      ) : null}
      {impact.employees.length ? (
        <CollapsibleGroup
          title="직원"
          count={`${impact.employees.length}명`}
          leading={<Users aria-hidden className="size-4" />}
        >
          {impact.employees.map((e) => (
            <GroupItem
              key={e.id}
              main={e.name}
              sub={[e.email, e.team_name ?? "팀 없음", e.position_name].join(" · ")}
            />
          ))}
        </CollapsibleGroup>
      ) : null}
      {registrations.length ? (
        <CollapsibleGroup
          title="운영진 가입 신청"
          count={`${registrations.length}건${registrationNote ? ` · ${registrationNote}` : ""}`}
          leading={<UserPlus aria-hidden className="size-4" />}
        >
          {registrations.map((r) => (
            <GroupItem
              key={r.id}
              main={r.applicant_name}
              sub={r.applicant_email}
              badge={
                <Badge variant={r.status === "PENDING" ? "warning" : "secondary"}>
                  {REGISTRATION_STATUS[r.status]}
                </Badge>
              }
            />
          ))}
        </CollapsibleGroup>
      ) : null}
      {bootcamps.length ? (
        <CollapsibleGroup
          title="담당 과정"
          count={`${bootcamps.length}개`}
          leading={<BookOpen aria-hidden className="size-4" />}
        >
          {bootcamps.map((b) => (
            <GroupItem key={b.id} main={b.name} />
          ))}
        </CollapsibleGroup>
      ) : null}
    </div>
  );
}
