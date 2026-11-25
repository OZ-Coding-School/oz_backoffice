import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { toast } from "sonner";

import { PanelHead, PanelList, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { ErrorState } from "@/components/error-state";
import { errorText } from "@/features/admin-org/text";
import { maskPhone } from "@/features/profile/mask";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { formatKst } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { ACCOUNT_TYPE_LABELS, ENROLLMENT_LABELS, memberQuery, useSetActive, type MemberDetail } from "../api";

const REASON_MAX = 300;
const at = (value: string | null | undefined, pattern = "yyyy.MM.dd") => (value ? formatKst(value, pattern) : "—");

/** 회원 패널 (F68·F71): 계정 / 종류별 연결 정보 / 이력. 머리에는 [비활성화] 또는 [활성화]만 */
export function MemberSheet({ userId, onClose }: { userId: string; onClose: () => void }) {
  const member = useQuery(memberQuery(userId));
  const access = useQuery(staffAccessQuery);
  const canManage = !!access.data && hasPermission(access.data, "member.user.manage");
  const [confirming, setConfirming] = useState(false);
  const m = member.data;
  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined}>
        <PanelHead
          title={m?.name ?? "회원"}
          description={m?.email ?? ""}
          badges={
            m ? (
              <>
                <Badge variant="outline">{ACCOUNT_TYPE_LABELS[m.account_type]}</Badge>
                {m.is_super_admin ? <Badge variant="primary">최고 관리자</Badge> : null}
                {m.is_active ? null : <Badge variant="secondary">비활성</Badge>}
              </>
            ) : null
          }
          actions={
            m && canManage ? (
              <Button
                variant="outline"
                size="sm"
                className={cn(
                  m.is_active &&
                    "border-destructive-text text-destructive-text hover:bg-destructive-subtle hover:text-destructive-text",
                )}
                onClick={() => setConfirming(true)}
              >
                {m.is_active ? "비활성화" : "활성화"}
              </Button>
            ) : null
          }
          onClose={onClose}
        />
        {member.isPending ? (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        ) : member.isError || !m ? (
          <ErrorState className="m-6" onRetry={() => void member.refetch()} />
        ) : (
          <MemberView member={m} />
        )}
        {confirming && m ? <ActiveDialog member={m} onClose={() => setConfirming(false)} /> : null}
      </SheetContent>
    </Sheet>
  );
}

function MemberView({ member: m }: { member: MemberDetail }) {
  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
      <PanelSection title="계정">
        <PanelRow label="이메일">
          <span className="break-all">{m.email}</span>
        </PanelRow>
        <PanelRow label="휴대폰">{maskPhone(m.phone_number) ?? "—"}</PanelRow>
        <PanelRow label="승인일">{at(m.approved_at)}</PanelRow>
        <PanelRow label="마지막 로그인">{at(m.last_login_at, "yyyy.MM.dd HH:mm")}</PanelRow>
        <PanelRow label="상태">
          <Badge variant={m.is_active ? "success" : "secondary"}>{m.is_active ? "활성" : "비활성"}</Badge>
        </PanelRow>
      </PanelSection>
      {m.account_type === "STUDENT" ? (
        <PanelSection title="수강">
          {m.enrollments.length ? (
            <ul aria-label="수강" className="divide-y divide-border overflow-hidden rounded-md border border-border">
              {m.enrollments.map((e) => (
                <li
                  key={`${e.bootcamp_name}-${e.cohort_number}`}
                  className="flex min-h-10 items-center gap-2 px-3 py-2"
                >
                  <span className="min-w-0 flex-1 truncate text-body text-foreground">
                    {e.bootcamp_name} {e.cohort_number}기
                  </span>
                  <Badge variant={e.status === "ENROLLED" ? "info" : "secondary"}>
                    {ENROLLMENT_LABELS[e.status] ?? e.status}
                  </Badge>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-body text-muted-foreground">수강 기수가 없어요.</p>
          )}
        </PanelSection>
      ) : null}
      {m.account_type === "MENTOR" ? (
        <PanelSection title="배정">
          <PanelRow label="계약">{m.contract_count ?? 0}건</PanelRow>
          {m.assignments.length ? (
            <ul aria-label="배정" className="divide-y divide-border overflow-hidden rounded-md border border-border">
              {m.assignments.map((a) => (
                <li
                  key={`${a.bootcamp_name}-${a.cohort_number}`}
                  className="flex min-h-10 items-center gap-2 px-3 py-2"
                >
                  <span className="min-w-0 flex-1 truncate text-body text-foreground">
                    {a.bootcamp_name} {a.cohort_number}기
                  </span>
                  <Badge variant={a.active ? "info" : "secondary"}>{a.active ? "배정 중" : "종료"}</Badge>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-body text-muted-foreground">배정된 기수가 없어요.</p>
          )}
        </PanelSection>
      ) : null}
      {m.account_type === "STAFF" ? (
        <PanelSection title="소속">
          {m.department_name ? (
            <>
              <PanelRow label="부서">{m.department_name}</PanelRow>
              <PanelRow label="팀">{m.team_name ?? "팀 없음"}</PanelRow>
              <PanelRow label="직위">{m.position_name ?? "—"}</PanelRow>
            </>
          ) : (
            <p className="text-body text-muted-foreground">직원 정보가 없어요.</p>
          )}
        </PanelSection>
      ) : null}
      {m.history.length ? (
        <PanelSection title="이력">
          <PanelList
            label="이력"
            items={m.history.map((h, i) => ({
              id: `${h.at}-${i}`,
              name: `${h.action === "DEACTIVATE" ? "비활성화" : "활성화"}${h.actor_name ? ` · ${h.actor_name}` : ""}`,
              meta: `${formatKst(h.at, "M/d HH:mm")}${h.reason ? ` · ${h.reason}` : ""}`,
            }))}
          />
        </PanelSection>
      ) : null}
    </div>
  );
}

/** 비활성화(사유 필수)·활성화(사유 선택) 확인 (A94·F71) */
function ActiveDialog({ member, onClose }: { member: MemberDetail; onClose: () => void }) {
  const id = useId();
  const deactivate = member.is_active;
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const save = useSetActive(member.id);
  const onConfirm = async () => {
    setError(null);
    try {
      await save.mutateAsync({ active: !deactivate, reason });
      toast.success(deactivate ? `${member.name} 계정을 비활성화했어요` : `${member.name} 계정을 활성화했어요`);
      onClose();
    } catch (e) {
      setError(errorText(e));
    }
  };
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-120 flex-col gap-4 p-6">
        <DialogTitle className="pr-8 text-h2 text-foreground">
          {member.name} 계정을 {deactivate ? "비활성화" : "활성화"}할까요?
        </DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          {deactivate
            ? "로그인할 수 없게 되고, 로그인 중인 기기에서도 바로 로그아웃돼요. 나중에 다시 활성화할 수 있어요."
            : "다시 로그인할 수 있게 돼요."}
        </DialogDescription>
        <div className="flex flex-col gap-1.5">
          <label htmlFor={`${id}-reason`} className="text-label text-foreground">
            {deactivate ? "비활성화 사유" : "활성화 사유 (선택)"}
          </label>
          <Textarea
            id={`${id}-reason`}
            rows={4}
            maxLength={REASON_MAX}
            placeholder="사유를 적어 주세요 (처리 이력에 남아요)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <span className="self-end text-caption text-muted-foreground">
            {reason.length} / {REASON_MAX}
          </span>
        </div>
        {error ? <Alert variant="error" title={error} /> : null}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            취소
          </Button>
          <Button
            variant={deactivate ? "destructive" : "primary"}
            disabled={save.isPending || (deactivate && !reason.trim())}
            onClick={() => void onConfirm()}
          >
            {deactivate ? "비활성화" : "활성화"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
