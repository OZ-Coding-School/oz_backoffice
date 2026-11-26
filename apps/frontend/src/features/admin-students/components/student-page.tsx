import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, CircleCheck, History, Hourglass, IdCard, Users, Wallet } from "lucide-react";
import type { ReactNode } from "react";

import { StatTile } from "@/components/stat-tile";
import { SectionCard } from "@/components/section-card";
import { ProfileHero } from "@/components/profile-hero";
import { ErrorState } from "@/components/error-state";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { RECEIVED_STATUS, desiredLabel } from "@/features/mentor-requests/labels";
import { maskPhone } from "@/features/profile/mask";
import { STATUS_STYLE } from "@/features/sessions/labels";
import { hasPermission, staffAccessQuery, type StaffCohort } from "@/features/staff/api";
import { formatKst, formatKstDay, formatMinutes } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { recentQuery, studentQuery, type RecentItem, type StudentDetail } from "../api";
import { dot, ENROLLMENT, HRD_STATUS } from "../labels";

export type StudentTab = "basic" | "mentoring";

const TABS: { value: StudentTab; label: string }[] = [
  { value: "basic", label: "기본 정보" },
  { value: "mentoring", label: "멘토링" },
];

/** 학사 > 수강생 상세 (F76): 머리 + 탭 기본 정보·멘토링 */
export function StudentPage({ studentId, cohortId, tab }: { studentId: string; cohortId: string; tab: StudentTab }) {
  const detail = useQuery(studentQuery(cohortId, studentId));
  const access = useQuery(staffAccessQuery);
  const cohort = access.data?.cohorts.find((c) => c.id === cohortId);
  const s = detail.data;
  return (
    <div className="flex flex-col gap-5">
      <Link
        to="/admin/academy/students"
        search={{ cohort: cohortId }}
        className="inline-flex w-fit items-center gap-1.5 text-body text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft aria-hidden className="size-4" />
        수강생
      </Link>
      {detail.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : detail.isError || !s ? (
        <ErrorState onRetry={() => void detail.refetch()} />
      ) : (
        <>
          <Head student={s} cohort={cohort} />
          <nav aria-label="수강생 상세">
            <ul className="flex gap-1 border-b border-border">
              {TABS.map((t) => (
                <li key={t.value}>
                  <Link
                    to="/admin/academy/students/$studentId"
                    params={{ studentId }}
                    search={{ cohort: cohortId, ...(t.value === "basic" ? {} : { tab: t.value }) }}
                    aria-current={t.value === tab ? "page" : undefined}
                    className={cn(
                      "-mb-px inline-flex h-10 items-center border-b-2 px-3 text-body outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      t.value === tab
                        ? "border-primary text-primary-text"
                        : "border-transparent text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {t.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          {tab === "basic" ? (
            <BasicTab student={s} cohort={cohort} />
          ) : (
            <MentoringTab
              student={s}
              cohortId={cohortId}
              canSeeRecent={!!access.data && hasPermission(access.data, "mentoring.request.read")}
            />
          )}
        </>
      )}
    </div>
  );
}

const cohortName = (cohort: StaffCohort | undefined) =>
  cohort ? `${cohort.bootcamp_name} ${cohort.cohort_number}기` : "—";

function Head({ student: s, cohort }: { student: StudentDetail; cohort: StaffCohort | undefined }) {
  const status = ENROLLMENT[s.status];
  return (
    <ProfileHero
      name={s.name}
      badges={
        <>
          <Badge variant={status.badge}>{status.label}</Badge>
          <Badge variant={s.member ? "default" : "outline"}>{s.member ? "가입함" : "미가입"}</Badge>
        </>
      }
      description={[cohortName(cohort), s.email].filter(Boolean).join(" · ")}
    />
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[112px_minmax(0,1fr)] items-center gap-3">
      <dt className="text-body text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-body-strong text-foreground">{children}</dd>
    </div>
  );
}

function BasicTab({ student: s, cohort }: { student: StudentDetail; cohort: StaffCohort | undefined }) {
  const status = ENROLLMENT[s.status];
  return (
    <SectionCard icon={IdCard} title="기본 · 수강 정보" description="Airtable 명단과 가입 계정 정보예요.">
      <dl className="flex flex-col gap-3">
        <Row label="이름">{s.name}</Row>
        <Row label="휴대폰">{maskPhone(s.phone_number) ?? "—"}</Row>
        <Row label="이메일">{s.email ?? "—"}</Row>
        <Row label="기수">{cohortName(cohort)}</Row>
        <Row label="수강 상태">
          <Badge variant={status.badge}>{status.label}</Badge>
        </Row>
        <Row label="HRD 상태">{HRD_STATUS[s.hrd_net_status] ?? s.hrd_net_status}</Row>
        <Row label="수강 시작">{dot(s.enrolled_at)}</Row>
        {s.ended_at ? <Row label="수강 종료">{dot(s.ended_at)}</Row> : null}
        {s.end_reason ? <Row label="종료 사유">{s.end_reason}</Row> : null}
        <Row label="가입 계정">
          {s.member
            ? [s.member.approved_at ? `${formatKst(s.member.approved_at, "yyyy.MM.dd")} 승인` : null, s.member.email]
                .filter(Boolean)
                .join(" · ")
            : "미가입"}
        </Row>
        <Row label="명단 원천">
          {s.airtable_record_id ? "Airtable" : "직접 등록"}
          {s.synced_at ? ` · ${formatKst(s.synced_at, "M/d HH:mm")} 동기화` : ""}
        </Row>
      </dl>
    </SectionCard>
  );
}

function MentoringTab({
  student: s,
  cohortId,
  canSeeRecent,
}: {
  student: StudentDetail;
  cohortId: string;
  canSeeRecent: boolean;
}) {
  const m = s.mentoring;
  const a = m.account;
  const recent = useQuery({ ...recentQuery(cohortId, s.id), enabled: canSeeRecent });
  return (
    <div className="flex flex-col gap-4">
      <section aria-label="멘토링 요약" className="grid grid-cols-4 gap-3">
        <StatTile
          icon={Wallet}
          label="잔여"
          value={a ? formatMinutes(a.remaining_minutes) : "지급 전"}
          hint={a?.is_expired ? "기간이 끝난 계좌예요" : "바로 신청할 수 있는 시간"}
        />
        <StatTile
          icon={Hourglass}
          label="보류"
          value={a ? formatMinutes(a.held_minutes) : "—"}
          hint={`대기 중인 신청 ${m.pending_request_count}건`}
        />
        <StatTile
          icon={CircleCheck}
          label="사용"
          value={a ? formatMinutes(a.used_minutes) : "—"}
          hint={`완료 세션 ${m.completed_session_count}회 · 예정 ${m.upcoming_session_count}회`}
        />
        <StatTile
          icon={Users}
          label="팀"
          value={m.team_label ?? "없음"}
          hint={m.team_label ? "팀 멘토링 참여" : "1:1 멘토링만"}
        />
      </section>
      {canSeeRecent ? (
        <SectionCard icon={History} title="최근 신청·세션" description="최근 3건" bodyClassName="gap-0 p-0 md:p-0">
          {recent.isPending ? (
            <div className="flex justify-center py-6">
              <Spinner />
            </div>
          ) : recent.isError ? (
            <ErrorState className="m-4" onRetry={() => void recent.refetch()} />
          ) : recent.data.length === 0 ? (
            <p className="px-4 py-6 text-center text-body text-muted-foreground">신청·세션이 없어요.</p>
          ) : (
            <div role="table" aria-label="최근 신청·세션">
              <div
                role="row"
                className="grid grid-cols-[140px_minmax(0,1fr)_120px_72px_72px] gap-3 border-t border-border bg-muted px-4 py-2 text-caption text-muted-foreground"
              >
                {["일시", "내용", "멘토", "구분", "상태"].map((h) => (
                  <span key={h} role="columnheader">
                    {h}
                  </span>
                ))}
              </div>
              {recent.data.map((item) => (
                <RecentRow
                  key={`${item.kind}-${item.kind === "request" ? item.request.id : item.session.id}`}
                  item={item}
                />
              ))}
            </div>
          )}
        </SectionCard>
      ) : null}
    </div>
  );
}

function RecentRow({ item }: { item: RecentItem }) {
  const cols =
    "grid grid-cols-[140px_minmax(0,1fr)_120px_72px_72px] items-center gap-3 border-t border-border px-4 py-3";
  if (item.kind === "request") {
    const r = item.request;
    const status = RECEIVED_STATUS[r.status];
    return (
      <div role="row" className={cols}>
        <span role="cell" className="text-body text-foreground">
          {desiredLabel(r)}
        </span>
        <span role="cell" className="flex min-w-0 flex-col">
          <span className="truncate text-body-strong text-foreground">{r.topic}</span>
          <span className="text-caption text-muted-foreground">{r.duration}분</span>
        </span>
        <span role="cell" className="truncate text-body text-foreground">
          {r.mentor_display_name}
        </span>
        <span role="cell" className="text-body text-foreground">
          신청
        </span>
        <span role="cell">
          <Badge variant={status.badge}>{status.label}</Badge>
        </span>
      </div>
    );
  }
  const s = item.session;
  const status = STATUS_STYLE[s.status];
  return (
    <div role="row" className={cols}>
      <span role="cell" className="text-body text-foreground">
        {formatKstDay(s.starts_at)} {formatKst(s.starts_at, "HH:mm")}
      </span>
      <span role="cell" className="flex min-w-0 flex-col">
        <span className="truncate text-body-strong text-foreground">{s.topic}</span>
        <span className="text-caption text-muted-foreground">
          {s.record_duration_minutes
            ? `기록 ${s.record_duration_minutes}분`
            : s.team_label
              ? `팀 · ${s.team_label}`
              : "1:1"}
        </span>
      </span>
      <span role="cell" className="truncate text-body text-foreground">
        {s.mentor_display_name}
      </span>
      <span role="cell" className="text-body text-foreground">
        세션
      </span>
      <span role="cell">
        <Badge variant={status.badge}>{status.label}</Badge>
      </span>
    </div>
  );
}
