import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { maskPhone } from "@/features/profile/mask";
import { cn } from "@/lib/utils";

import { candidatesQuery, useApprove, useReject, type Applicant, type StudentCandidate } from "../api";
import { contractStatusLabel, enrollmentLabel, matchTag, requestedCohort, studentCandidateCohort } from "../labels";

export const REJECT_REASON_MAX = 300;

const ERRORS: Record<string, string> = {
  student_already_claimed: "이미 다른 회원과 연결된 명단이에요. 다른 명단을 골라 주세요.",
  student_removed_in_source: "원천(Airtable)에서 삭제된 명단이에요.",
  contract_not_linkable: "연결할 수 없는 계약이 있어요. 목록을 다시 불러 주세요.",
  signup_not_found: "이미 처리된 신청이에요.",
  permission_denied: "이 신청을 처리할 권한이 없어요.",
};

function errorMessage(e: unknown, fallback: string): string {
  const code = e instanceof ApiError ? e.code : undefined;
  return (code && ERRORS[code]) ?? fallback;
}

/** 입력이 멈추고 0.3초 뒤의 값 (후보 검색) */
function useDebounced(value: string, ms = 300): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

function Shell({
  title,
  description,
  onClose,
  children,
  footer,
}: {
  title: string;
  description: string;
  onClose: () => void;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-150 flex-col gap-4 p-6">
        <div className="flex flex-col gap-1 pr-8">
          <DialogTitle className="text-h2 text-foreground">{title}</DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">{description}</DialogDescription>
        </div>
        {children}
        <div className="flex justify-end gap-2">{footer}</div>
      </DialogContent>
    </Dialog>
  );
}

function ApplicantSummary({ applicant }: { applicant: Applicant }) {
  return (
    <dl className="grid grid-cols-[auto_auto_1fr] gap-x-6 gap-y-0.5 rounded-lg bg-muted px-4 py-3">
      <dt className="text-caption text-muted-foreground">신청 이름</dt>
      <dt className="text-caption text-muted-foreground">인증 휴대폰</dt>
      <dt className="text-caption text-muted-foreground">이메일</dt>
      <dd className="text-body-strong text-foreground">{applicant.name}</dd>
      <dd className="text-body-strong text-foreground">{maskPhone(applicant.phone_number) ?? "—"}</dd>
      <dd className="break-all text-body-strong text-foreground">{applicant.email}</dd>
    </dl>
  );
}

function CandidateSearch({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="relative">
      <Search aria-hidden className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        aria-label="후보 검색"
        placeholder="이름 또는 휴대폰으로 찾기"
        value={value}
        maxLength={50}
        onChange={(e) => onChange(e.target.value)}
        className="pl-9"
      />
    </div>
  );
}

const ROW = "flex items-center gap-3 border-b border-border px-4 py-3 last:border-b-0";

/** 수강생 승인 (A33·A82): 담당 범위의 미가입 명단 하나를 골라 연결한다. 다른 기수·불일치도 가능 */
export function ApproveStudentDialog({ applicant, onClose }: { applicant: Applicant; onClose: () => void }) {
  const [q, setQ] = useState("");
  const query = useDebounced(q.trim());
  const found = useQuery({ ...candidatesQuery(applicant.user_id, query), placeholderData: keepPreviousData });
  const [selected, setSelected] = useState<StudentCandidate | null>(null);
  const approve = useApprove(applicant.user_id);
  const [error, setError] = useState<string | null>(null);
  const candidates = found.data?.students ?? [];

  const submit = async () => {
    if (!selected) return;
    setError(null);
    try {
      await approve.mutateAsync({ student_id: selected.student_id });
      toast.success(`${applicant.name}님 가입을 승인했어요`);
      onClose();
    } catch (e) {
      setError(errorMessage(e, "승인하지 못했어요. 잠시 후 다시 시도해 주세요."));
    }
  };

  return (
    <Shell
      title={`가입 승인 · ${applicant.name}`}
      description={`연결할 수강생 명단을 고르세요. 신청 기수는 ${requestedCohort(applicant)}예요.`}
      onClose={onClose}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            취소
          </Button>
          <Button disabled={!selected || approve.isPending} onClick={() => void submit()}>
            연결하고 승인
          </Button>
        </>
      }
    >
      <ApplicantSummary applicant={applicant} />
      <CandidateSearch value={q} onChange={setQ} />
      {found.isPending ? (
        <div className="flex justify-center py-6">
          <Spinner />
        </div>
      ) : candidates.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border py-6 text-center text-body text-muted-foreground">
          {query ? "찾는 명단이 없어요." : "이름이나 휴대폰이 같은 명단이 없어요. 이름으로 찾아보세요."}
        </p>
      ) : (
        <RadioGroup
          aria-label="연결할 명단"
          value={selected?.student_id ?? ""}
          onValueChange={(id) => setSelected(candidates.find((c) => c.student_id === id) ?? null)}
          className="flex max-h-72 flex-col gap-0 overflow-y-auto rounded-lg border border-border"
        >
          {candidates.map((c) => (
            <div key={c.student_id} className={cn(ROW, selected?.student_id === c.student_id && "bg-accent/50")}>
              <RadioGroupItem value={c.student_id} aria-label={`${c.name} ${studentCandidateCohort(c)}`}>
                {""}
              </RadioGroupItem>
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="text-body-strong text-foreground">
                  {c.name} · {maskPhone(c.phone_number) ?? "—"}
                </span>
                <span className="text-caption text-muted-foreground">
                  {[studentCandidateCohort(c), matchTag(c), c.same_cohort ? null : "다른 기수"]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </span>
              <Badge variant={c.enrollment_status === "ENROLLED" ? "success" : "secondary"}>
                {enrollmentLabel(c.enrollment_status)}
              </Badge>
            </div>
          ))}
        </RadioGroup>
      )}
      {selected && !selected.same_cohort ? (
        <Alert
          variant="warning"
          title="다른 기수의 명단이에요"
          description={`연결하면 STUDENT 역할은 ${studentCandidateCohort(selected)} 범위로 부여돼요. 연결 기록은 감사 로그에 남아요.`}
        />
      ) : null}
      {selected && selected.same_cohort && !(selected.name_match && selected.phone_match) ? (
        <Alert
          variant="warning"
          title="이름이나 휴대폰이 달라요"
          description="같은 사람인지 확인한 뒤 연결해 주세요. 연결 기록은 감사 로그에 남아요."
        />
      ) : null}
      {error ? <Alert variant="error" title={error} /> : null}
    </Shell>
  );
}

/** 멘토 승인 (A33·A82): 미연결 멘토 계약을 0개 이상 골라 연결한다 */
export function ApproveMentorDialog({ applicant, onClose }: { applicant: Applicant; onClose: () => void }) {
  const [q, setQ] = useState("");
  const query = useDebounced(q.trim());
  const found = useQuery({ ...candidatesQuery(applicant.user_id, query), placeholderData: keepPreviousData });
  const [selected, setSelected] = useState<string[]>([]);
  const approve = useApprove(applicant.user_id);
  const [error, setError] = useState<string | null>(null);
  const contracts = found.data?.contracts ?? [];

  const submit = async () => {
    setError(null);
    try {
      await approve.mutateAsync({ contract_ids: selected });
      toast.success(`${applicant.name}님 가입을 승인했어요`);
      onClose();
    } catch (e) {
      setError(errorMessage(e, "승인하지 못했어요. 잠시 후 다시 시도해 주세요."));
    }
  };

  return (
    <Shell
      title={`가입 승인 · ${applicant.name}`}
      description="연결할 멘토 계약을 고르세요. 고르지 않아도 승인할 수 있어요."
      onClose={onClose}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            취소
          </Button>
          <Button disabled={approve.isPending} onClick={() => void submit()}>
            {selected.length ? `계약 ${selected.length}개 연결하고 승인` : "계약 없이 승인"}
          </Button>
        </>
      }
    >
      <ApplicantSummary applicant={applicant} />
      <CandidateSearch value={q} onChange={setQ} />
      {found.isPending ? (
        <div className="flex justify-center py-6">
          <Spinner />
        </div>
      ) : contracts.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border py-6 text-center text-body text-muted-foreground">
          {query ? "찾는 계약이 없어요." : "이름이나 휴대폰이 같은 미연결 계약이 없어요."}
        </p>
      ) : (
        <ul aria-label="연결할 계약" className="flex max-h-72 flex-col overflow-y-auto rounded-lg border border-border">
          {contracts.map((c) => {
            const checked = selected.includes(c.contract_id);
            return (
              <li key={c.contract_id}>
                <label className={cn(ROW, "cursor-pointer", checked && "bg-accent/50")}>
                  <Checkbox
                    checked={checked}
                    aria-label={`${c.title} 연결`}
                    onCheckedChange={(on) =>
                      setSelected((prev) => (on ? [...prev, c.contract_id] : prev.filter((id) => id !== c.contract_id)))
                    }
                  />
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="text-body-strong text-foreground">
                      {c.contractor_name} · {maskPhone(c.contractor_phone) ?? "—"}
                    </span>
                    <span className="text-caption text-muted-foreground">
                      {[
                        c.title,
                        `${c.start_date.replaceAll("-", ".")} ~ ${c.end_date.replaceAll("-", ".")}`,
                        matchTag(c),
                      ].join(" · ")}
                    </span>
                  </span>
                  <Badge variant={c.status === "ACTIVE" ? "success" : "secondary"}>
                    {contractStatusLabel(c.status)}
                  </Badge>
                </label>
              </li>
            );
          })}
        </ul>
      )}
      {error ? <Alert variant="error" title={error} /> : null}
    </Shell>
  );
}

/** 반려 (A33): 사유 필수 300자. 신청자에게 메일로 알린다 */
export function RejectDialog({ applicant, onClose }: { applicant: Applicant; onClose: () => void }) {
  const [reason, setReason] = useState("");
  const reject = useReject(applicant.user_id);
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    setError(null);
    try {
      await reject.mutateAsync(reason.trim());
      toast.success(`${applicant.name}님 가입을 반려했어요`);
      onClose();
    } catch (e) {
      setError(errorMessage(e, "반려하지 못했어요. 잠시 후 다시 시도해 주세요."));
    }
  };
  return (
    <Shell
      title={`가입 반려 · ${applicant.name}`}
      description="반려 사유는 신청자에게 메일로 보내져요. 신청자는 다시 신청할 수 있어요."
      onClose={onClose}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            취소
          </Button>
          <Button variant="destructive" disabled={!reason.trim() || reject.isPending} onClick={() => void submit()}>
            반려
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-1.5">
        <Textarea
          aria-label="반려 사유"
          placeholder="예: 수강생 명단에서 찾을 수 없어요. 신청한 기수를 확인해 주세요."
          value={reason}
          maxLength={REJECT_REASON_MAX}
          rows={4}
          onChange={(e) => setReason(e.target.value)}
        />
        <p className="text-right text-caption text-muted-foreground">
          {reason.length} / {REJECT_REASON_MAX}
        </p>
      </div>
      {error ? <Alert variant="error" title={error} /> : null}
    </Shell>
  );
}
