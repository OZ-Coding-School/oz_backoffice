import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";

import { ErrorState } from "@/components/error-state";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { assignmentPeriod } from "@/features/mentor-profile/labels";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { cn } from "@/lib/utils";

import { mentorAssignmentsQuery, mentorQuery, type MentorAssignment, type MentorItem } from "../api";
import { endText, payText } from "../labels";
import { ActivationActions } from "./activation-actions";
import { AcceptingBadge, ActiveBadge } from "./mentors-page";
import { ProfileTab } from "./profile-tab";

export type MentorTab = "profile" | "assignments";

const TABS: { value: MentorTab; label: string }[] = [
  { value: "profile", label: "프로필" },
  { value: "assignments", label: "배정" },
];

/** 강사·멘토 > 멘토 상세 (F79): 머리 + 탭 프로필·배정 */
export function MentorPage({ mentorId, tab }: { mentorId: string; tab: MentorTab }) {
  const mentor = useQuery(mentorQuery(mentorId));
  const access = useQuery(staffAccessQuery);
  const canManage = !!access.data && hasPermission(access.data, "educator.mentor.manage");
  const m = mentor.data;
  return (
    <div className="flex flex-col gap-5">
      <Link
        to="/admin/educators/mentors"
        className="inline-flex w-fit items-center gap-1.5 text-body text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft aria-hidden className="size-4" />
        멘토
      </Link>
      {mentor.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : mentor.isError || !m ? (
        <ErrorState onRetry={() => void mentor.refetch()} />
      ) : (
        <>
          <Head mentor={m} actions={canManage ? <ActivationActions mentor={m} /> : null} />
          <nav aria-label="멘토 상세">
            <ul className="flex gap-1 border-b border-border">
              {TABS.map((t) => (
                <li key={t.value}>
                  <Link
                    to="/admin/educators/mentors/$mentorId"
                    params={{ mentorId }}
                    search={t.value === "profile" ? {} : { tab: t.value }}
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
          {tab === "profile" ? <ProfileTab mentor={m} canManage={canManage} /> : <AssignmentsTab mentorId={mentorId} />}
        </>
      )}
    </div>
  );
}

function Head({ mentor: m, actions }: { mentor: MentorItem; actions: ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <Avatar name={m.display_name || m.name} />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <h1 className="text-h1 text-foreground">{m.name}</h1>
          <ActiveBadge on={m.is_active} />
          <AcceptingBadge on={m.accepting_requests} />
        </div>
        <p className="truncate text-body text-muted-foreground">
          {[m.display_name !== m.name ? m.display_name : null, m.email].filter(Boolean).join(" · ")}
        </p>
      </div>
      {actions}
    </div>
  );
}

function AssignmentsTab({ mentorId }: { mentorId: string }) {
  const list = useQuery(mentorAssignmentsQuery(mentorId));
  if (list.isPending)
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  if (list.isError) return <ErrorState onRetry={() => void list.refetch()} />;
  if (list.data.length === 0)
    return (
      <p className="rounded-xl border border-border bg-card p-6 text-body text-muted-foreground">
        아직 배정된 기수가 없어요.
      </p>
    );
  return (
    <ul aria-label="배정" className="flex flex-col gap-3">
      {list.data.map((a) => (
        <AssignmentCard key={a.id} assignment={a} />
      ))}
    </ul>
  );
}

function AssignmentCard({ assignment: a }: { assignment: MentorAssignment }) {
  const end = endText(a);
  return (
    <li
      aria-label={`${a.bootcamp_name} ${a.cohort_number}기`}
      className={cn(
        "flex flex-col gap-2.5 rounded-xl border border-border p-5",
        a.is_active ? "bg-card" : "bg-muted/60 [&_dd]:text-muted-foreground",
      )}
    >
      <div className="flex items-center gap-2">
        <h2 className={cn("text-h3", a.is_active ? "text-foreground" : "text-muted-foreground")}>
          {a.bootcamp_name} {a.cohort_number}기
        </h2>
        <Badge variant={a.is_active ? "success" : "secondary"}>{a.is_active ? "배정 중" : "종료"}</Badge>
      </div>
      <dl className="grid grid-cols-[56px_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-body">
        <dt className="text-muted-foreground">기간</dt>
        <dd className="text-foreground">{assignmentPeriod(a)}</dd>
        <dt className="text-muted-foreground">정산</dt>
        <dd className="text-foreground">{payText(a)}</dd>
        {end ? (
          <>
            <dt className="text-muted-foreground">종료</dt>
            <dd className="text-foreground">{end}</dd>
          </>
        ) : null}
      </dl>
    </li>
  );
}
