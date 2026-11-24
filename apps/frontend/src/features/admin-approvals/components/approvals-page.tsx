import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { UserCheck } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LoadMore } from "@/components/load-more";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { Spinner } from "@/components/ui/spinner";
import { maskPhone } from "@/features/profile/mask";
import { StaffCohortSelect } from "@/features/staff/components/staff-cohort-select";
import { cn } from "@/lib/utils";

import { approvalCountQuery, approvalsQuery, type Applicant, type ApprovalTab } from "../api";
import { appliedAt, matchLabel, requestedCohort } from "../labels";
import { ApproveMentorDialog, ApproveStudentDialog, RejectDialog } from "./approval-dialogs";

const TABS: { value: ApprovalTab; label: string; type: "STUDENT" | "MENTOR" }[] = [
  { value: "student", label: "수강생", type: "STUDENT" },
  { value: "mentor", label: "멘토", type: "MENTOR" },
];

type Action = { kind: "approve" | "reject"; applicant: Applicant } | null;

/** 회원 가입 승인 (Figma `가입 승인 (FE-15a)`, F60·A33·A82). 데스크톱만(F58) */
export function ApprovalsPage({ tab, cohortId }: { tab: ApprovalTab; cohortId: string | undefined }) {
  const list = useInfiniteQuery(approvalsQuery(tab, cohortId));
  const students = useQuery(approvalCountQuery("STUDENT", cohortId));
  const mentors = useQuery(approvalCountQuery("MENTOR"));
  const navigate = useNavigate();
  const [action, setAction] = useState<Action>(null);
  const access = useQuery(staffAccessQuery);
  // 수강생은 회원 가입 승인 관리, 멘토는 계약 관리가 있어야 승인·반려 (A33·A86)
  const canDecide = access.data
    ? hasPermission(access.data, tab === "student" ? "member.approval.manage" : "educator.contract.manage")
    : false;
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const counts = { student: students.data, mentor: mentors.data };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">가입 승인</h1>
        <p className="text-body text-muted-foreground">자동 매칭되지 않은 가입 신청을 확인해 명단·계약에 연결해요.</p>
      </div>
      <div className="flex items-end gap-3">
        <nav aria-label="가입 유형" className="flex-1">
          <ul className="flex gap-1 border-b border-border">
            {TABS.map((t) => {
              const active = t.value === tab;
              const count = counts[t.value];
              return (
                <li key={t.value}>
                  <Link
                    to="/admin/members/approvals"
                    search={{
                      ...(t.value === "mentor" ? { type: "mentor" as const } : {}),
                      ...(cohortId && t.value === "student" ? { cohort: cohortId } : {}),
                    }}
                    activeOptions={{ exact: true, includeSearch: true }}
                    aria-current={active ? "page" : undefined}
                    aria-label={count === undefined ? t.label : `${t.label} ${count}`}
                    className={cn(
                      "-mb-px inline-flex h-10 items-center gap-1.5 border-b-2 px-3 text-body outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      active
                        ? "border-primary text-primary-text"
                        : "border-transparent text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {t.label}
                    {count === undefined ? null : <span>· {count}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        {tab === "student" ? (
          <StaffCohortSelect
            value={cohortId}
            onChange={(cohort) => void navigate({ to: "/admin/members/approvals", search: cohort ? { cohort } : {} })}
          />
        ) : null}
      </div>
      {list.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : list.isError ? (
        <ErrorState onRetry={() => void list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState icon={UserCheck} title="처리할 가입 신청이 없어요" />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <table className="w-full text-left text-body">
            <thead className="bg-muted text-caption text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  이름
                </th>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  이메일
                </th>
                <th scope="col" className="w-36 px-4 py-2.5 font-normal">
                  휴대폰
                </th>
                {tab === "student" ? (
                  <th scope="col" className="w-48 px-4 py-2.5 font-normal">
                    신청 기수
                  </th>
                ) : null}
                <th scope="col" className="w-32 px-4 py-2.5 font-normal">
                  자동 매칭
                </th>
                <th scope="col" className="w-24 px-4 py-2.5 font-normal">
                  신청일
                </th>
                {canDecide ? (
                  <th scope="col" className="w-40 px-4 py-2.5">
                    <span className="sr-only">동작</span>
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {items.map((a) => {
                const match = matchLabel(a);
                return (
                  <tr key={a.user_id} className="border-t border-border">
                    <td className="px-4 py-3 text-body-strong text-foreground">{a.name}</td>
                    <td className="px-4 py-3 break-all text-foreground">{a.email}</td>
                    <td className="px-4 py-3 text-muted-foreground">{maskPhone(a.phone_number) ?? "—"}</td>
                    {tab === "student" ? <td className="px-4 py-3 text-foreground">{requestedCohort(a)}</td> : null}
                    <td className="px-4 py-3">
                      <Badge variant={match.badge}>{match.label}</Badge>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{appliedAt(a)}</td>
                    {canDecide ? (
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            aria-label={`${a.name} 반려`}
                            onClick={() => setAction({ kind: "reject", applicant: a })}
                          >
                            반려
                          </Button>
                          <Button
                            size="sm"
                            aria-label={`${a.name} 승인`}
                            onClick={() => setAction({ kind: "approve", applicant: a })}
                          >
                            승인
                          </Button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {list.hasNextPage ? (
        <LoadMore
          loading={list.isFetchingNextPage}
          label="다음 신청을 불러오는 중…"
          onVisible={() => void list.fetchNextPage()}
        />
      ) : null}
      {action?.kind === "approve" && action.applicant.signup.signup_type === "STUDENT" ? (
        <ApproveStudentDialog applicant={action.applicant} onClose={() => setAction(null)} />
      ) : null}
      {action?.kind === "approve" && action.applicant.signup.signup_type === "MENTOR" ? (
        <ApproveMentorDialog applicant={action.applicant} onClose={() => setAction(null)} />
      ) : null}
      {action?.kind === "reject" ? <RejectDialog applicant={action.applicant} onClose={() => setAction(null)} /> : null}
    </div>
  );
}
