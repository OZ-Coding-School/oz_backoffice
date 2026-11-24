import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { UserCog } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LoadMore } from "@/components/load-more";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { EMPLOYMENT_TYPE_LABELS } from "@/features/auth/messages";
import { assignmentLabel, staffOptionsQuery, type StaffOptions } from "@/features/auth/staff-api";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { formatKst } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import {
  pendingRegistrationsQuery,
  REGISTRATION_TABS,
  registrationsQuery,
  withAllCohorts,
  type AdminRegistration,
  type RegistrationTab,
} from "../api";
import { ReviewDialog } from "./review-dialog";

/** 운영진 승인 (Figma `운영진 승인 (FE-15b)`, F61·A11·A62). 데스크톱만(F58) */
export function RegistrationsPage({ tab }: { tab: RegistrationTab }) {
  const list = useInfiniteQuery(registrationsQuery(tab));
  const pending = useQuery(pendingRegistrationsQuery);
  const options = useQuery(staffOptionsQuery);
  const access = useQuery(staffAccessQuery);
  const [reviewing, setReviewing] = useState<AdminRegistration | null>(null);
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const labels = options.data ? withAllCohorts(options.data, access.data?.cohorts ?? []) : null;
  const processed = tab !== "pending";
  const canReview = access.data ? hasPermission(access.data, "staff.registration.manage") : false; // A86

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">운영진 승인</h1>
        <p className="text-body text-muted-foreground">운영진이 처음 로그인해 입력한 소속·담당을 확인하고 승인해요.</p>
      </div>
      <nav aria-label="처리 상태">
        <ul className="flex gap-1 border-b border-border">
          {REGISTRATION_TABS.map((t) => {
            const active = t.value === tab;
            const count = t.value === "pending" ? pending.data : undefined;
            return (
              <li key={t.value}>
                <Link
                  to="/admin/members/staff-registrations"
                  search={t.value === "pending" ? {} : { status: t.value }}
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
      {list.isPending || !labels ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : list.isError ? (
        <ErrorState onRetry={() => void list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState icon={UserCog} title={processed ? "처리한 신청이 없어요" : "처리할 운영진 신청이 없어요"} />
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
                <th scope="col" className="px-4 py-2.5 font-normal">
                  부서 · 팀
                </th>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  직위
                </th>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  고용 형태
                </th>
                <th scope="col" className="px-4 py-2.5 font-normal">
                  담당
                </th>
                <th scope="col" className="w-28 px-4 py-2.5 font-normal">
                  {processed ? "처리일" : "신청일"}
                </th>
                <th scope="col" className={cn("px-4 py-2.5", processed ? "font-normal" : "w-24")}>
                  {processed ? tab === "rejected" ? "반려 사유" : "" : <span className="sr-only">동작</span>}
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id} className="border-t border-border align-top">
                  <td className="px-4 py-3 text-body-strong text-foreground">{r.applicant?.name ?? "—"}</td>
                  <td className="px-4 py-3 break-all text-foreground">{r.applicant?.email ?? "—"}</td>
                  <td className="px-4 py-3 text-foreground">{orgLabel(labels, r)}</td>
                  <td className="px-4 py-3 text-foreground">
                    {labels.positions.find((p) => p.id === r.position_id)?.name ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-foreground">
                    {EMPLOYMENT_TYPE_LABELS[r.employment_type] ?? r.employment_type}
                  </td>
                  <td className="px-4 py-3 text-foreground">{assignmentsLabel(labels, r)}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {dateOf(processed ? r.reviewed_at : r.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    {processed ? (
                      <span className="text-body-sm text-muted-foreground">{r.reject_reason ?? ""}</span>
                    ) : canReview ? (
                      <div className="flex justify-end">
                        <Button
                          size="sm"
                          aria-label={`${r.applicant?.name ?? "신청"} 검토`}
                          onClick={() => setReviewing(r)}
                        >
                          검토
                        </Button>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
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
      {reviewing && labels ? (
        <ReviewDialog registration={reviewing} options={labels} onClose={() => setReviewing(null)} />
      ) : null}
    </div>
  );
}

function dateOf(iso: string | null | undefined): string {
  return iso ? formatKst(iso, "MM/dd") : "—";
}

function orgLabel(options: StaffOptions, r: AdminRegistration): string {
  const department = options.departments.find((d) => d.id === r.department_id)?.name ?? "—";
  const team = r.team_id ? (options.teams.find((t) => t.id === r.team_id)?.name ?? "—") : "부서 직속";
  return `${department} · ${team}`;
}

/** 담당: 첫 대상과 '외 N' (없으면 '없음') */
function assignmentsLabel(options: StaffOptions, r: AdminRegistration): string {
  const names = r.assignments.map((a) => assignmentLabel(options, a) ?? "—");
  if (!names.length) return "없음";
  return names.length > 1 ? `${names[0]} 외 ${names.length - 1}` : (names[0] ?? "—");
}
