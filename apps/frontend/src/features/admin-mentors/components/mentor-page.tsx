import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, Plus } from "lucide-react";
import type { ReactNode } from "react";

import { ErrorState } from "@/components/error-state";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { assignmentPeriod } from "@/features/mentor-profile/labels";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { cn } from "@/lib/utils";

import { STATUS as CONTRACT_STATUS, period } from "@/features/admin-contracts/labels";

import {
  mentorAssignmentsQuery,
  mentorContractsQuery,
  mentorQuery,
  type MentorAssignment,
  type MentorItem,
} from "../api";
import { endText, payText } from "../labels";
import { ActivationActions } from "./activation-actions";
import { AssignmentSheet } from "./assignment-sheet";
import { AcceptingBadge, StatusBadge } from "./mentors-page";
import { ProfileTab } from "./profile-tab";

export type MentorTab = "profile" | "assignments" | "contracts";

const TABS: { value: MentorTab; label: string }[] = [
  { value: "profile", label: "프로필" },
  { value: "assignments", label: "배정" },
  { value: "contracts", label: "계약" },
];

/** 강사·멘토 > 멘토 상세 (F79): 머리 + 탭 프로필·배정 */
export function MentorPage({
  mentorId,
  tab,
  assignment,
}: {
  mentorId: string;
  tab: MentorTab;
  /** 배정 패널: 배정 id 또는 new (F85) */
  assignment?: string;
}) {
  const mentor = useQuery(mentorQuery(mentorId));
  const access = useQuery(staffAccessQuery);
  const canManage = !!access.data && hasPermission(access.data, "educator.mentor.manage");
  // 계약 탭은 계약 조회 권한이 있을 때만 (F83)
  const tabs = TABS.filter(
    (t) => t.value !== "contracts" || (!!access.data && hasPermission(access.data, "educator.contract.read")),
  );
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
              {tabs.map((t) => (
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
          {tab === "profile" ? (
            <ProfileTab mentor={m} canManage={canManage} />
          ) : tab === "contracts" ? (
            <ContractsTab mentorId={mentorId} />
          ) : (
            <AssignmentsTab
              mentor={m}
              assignment={assignment}
              canManage={!!access.data && hasPermission(access.data, "mentoring.assignment.manage")}
            />
          )}
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
          <StatusBadge mentor={m} />
          {m.is_registered ? <AcceptingBadge on={m.accepting_requests} /> : null}
        </div>
        <p className="truncate text-body text-muted-foreground">
          {m.is_registered
            ? [m.display_name !== m.name ? m.display_name : null, m.email].filter(Boolean).join(" · ")
            : "가입 전 · 계약을 먼저 만든 멘토예요"}
        </p>
      </div>
      {actions}
    </div>
  );
}

/** 배정 탭 (F79·F85): 카드를 세로로, [배정 추가]·카드 → 오른쪽 패널 */
function AssignmentsTab({
  mentor,
  assignment,
  canManage,
}: {
  mentor: MentorItem;
  assignment?: string;
  canManage: boolean;
}) {
  const navigate = useNavigate();
  const list = useQuery(mentorAssignmentsQuery(mentor.id));
  const open = (id?: string, replace = false) =>
    void navigate({
      to: "/admin/educators/mentors/$mentorId",
      params: { mentorId: mentor.id },
      search: { tab: "assignments", ...(id ? { assignment: id } : {}) },
      replace,
      ...(replace ? { ignoreBlocker: true } : {}),
    });
  // 가입 전·비활성 멘토는 새 배정을 받을 수 없다 (A35·A104)
  const canAdd = canManage && mentor.is_registered && mentor.is_active;
  if (list.isPending)
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  if (list.isError) return <ErrorState onRetry={() => void list.refetch()} />;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-body text-muted-foreground">
        {list.data.length ? `배정 ${list.data.length}건 · 활성 먼저` : "아직 배정된 기수가 없어요."}
      </p>
      {canAdd ? (
        // 카드 목록 맨 위의 점선 추가 카드 (F85 보완): 목록과 같은 폭·모서리로 이어 보이게
        <button
          type="button"
          onClick={() => open("new")}
          className="flex items-center justify-center gap-2 rounded-xl border border-dashed border-primary/40 bg-sidebar-accent/40 px-5 py-4 text-body-strong text-sidebar-accent-foreground outline-none transition-colors hover:border-primary/70 hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Plus aria-hidden className="size-4" />
          배정 추가
        </button>
      ) : null}
      {list.data.length ? (
        <ul aria-label="배정" className="flex flex-col gap-3">
          {list.data.map((a) => (
            <AssignmentCard key={a.id} assignment={a} mentorId={mentor.id} selected={a.id === assignment} />
          ))}
        </ul>
      ) : null}
      {assignment ? (
        <AssignmentSheet
          key={assignment}
          mentor={mentor}
          assignmentId={assignment}
          canManage={canManage}
          onOpen={(id) => open(id, true)}
          onClose={() => open()}
        />
      ) : null}
    </div>
  );
}

function AssignmentCard({
  assignment: a,
  mentorId,
  selected,
}: {
  assignment: MentorAssignment;
  mentorId: string;
  selected: boolean;
}) {
  const end = endText(a);
  return (
    <li aria-label={`${a.bootcamp_name} ${a.cohort_number}기`}>
      <Link
        to="/admin/educators/mentors/$mentorId"
        params={{ mentorId }}
        search={{ tab: "assignments", assignment: a.id }}
        className={cn(
          "flex flex-col gap-2.5 rounded-xl border border-border p-5 outline-none hover:bg-accent/60 focus-visible:ring-2 focus-visible:ring-ring",
          a.is_active ? "bg-card" : "bg-muted/60 [&_dd]:text-muted-foreground",
          selected && "border-primary/50 bg-accent",
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
      </Link>
    </li>
  );
}

/** 계약 탭 (F83): 조회만, 누르면 행정 업무 › 계약의 그 패널 */
function ContractsTab({ mentorId }: { mentorId: string }) {
  const list = useQuery(mentorContractsQuery(mentorId));
  if (list.isPending)
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  if (list.isError) return <ErrorState onRetry={() => void list.refetch()} />;
  const items = list.data.items;
  if (items.length === 0)
    return (
      <p className="rounded-xl border border-border bg-card p-6 text-body text-muted-foreground">
        이 멘토의 계약이 없어요. 계약은 행정 업무 › 계약에서 추가해요.
      </p>
    );
  return (
    <div className="flex flex-col gap-3">
      <p className="text-body text-muted-foreground">
        계약 {items.length}건 · 최근 등록부터. 추가·변경은 행정 업무 › 계약에서 해요.
      </p>
      <ul aria-label="계약" className="flex flex-col gap-3">
        {items.map((c) => {
          const status = CONTRACT_STATUS[c.status];
          const closed = c.status === "ENDED" || c.status === "TERMINATED";
          return (
            <li key={c.id}>
              <Link
                to="/admin/administration/contracts"
                search={{ contract: c.id }}
                aria-label={c.title}
                className={cn(
                  "flex flex-col gap-2.5 rounded-xl border border-border p-5 outline-none hover:bg-accent/60 focus-visible:ring-2 focus-visible:ring-ring",
                  closed ? "bg-muted/60 [&_dd]:text-muted-foreground" : "bg-card",
                )}
              >
                <span className="flex items-center gap-2">
                  <span className={cn("text-h3", closed ? "text-muted-foreground" : "text-foreground")}>{c.title}</span>
                  <Badge variant={status.badge}>{status.label}</Badge>
                </span>
                <dl className="grid grid-cols-[56px_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-body">
                  <dt className="text-muted-foreground">기간</dt>
                  <dd className="text-foreground">{period(c)}</dd>
                  <dt className="text-muted-foreground">계약서</dt>
                  <dd className="truncate text-foreground">
                    {c.contract_file ? c.contract_file.file_name : "없음 · 확정하려면 계약서가 필요해요"}
                  </dd>
                  <dt className="text-muted-foreground">담당</dt>
                  <dd className="text-foreground">{c.manager_name ?? "—"}</dd>
                </dl>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
