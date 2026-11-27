import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Check, Ellipsis } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorState } from "@/components/error-state";
import { PanelHead, PanelRow, PanelSection } from "@/components/panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { maskPhone } from "@/features/profile/mask";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { formatKst } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import {
  amendmentFileUrl,
  amendmentsQuery,
  contractFileUrl,
  contractQuery,
  type Amendment,
  type Contract,
  type StepAction,
} from "../api";
import {
  academyText,
  amountText,
  dotDate,
  FIELD_LABELS,
  fieldValue,
  fileSize,
  FLOW,
  isVendor,
  linkedText,
  MENTOR_HELP,
  period,
  PRICE_UNIT_LABELS,
  SETTLEMENT_LABELS,
  STATUS,
  TERMINATION_LABELS,
  TIME_BASIS_LABELS,
  TYPE_LABELS,
  VAT_LABELS,
  won,
} from "../labels";
import { ContractEditForm } from "./contract-form";
import { ContractWizard } from "./contract-wizard";
import { CancelDialog, DeleteDialog, ManagerDialog, StepDialog, TerminateDialog } from "./dialogs";
import { MoveDialog } from "./pickers";

/** 계약 패널 (F83·F96): 조회·상태 단계·수정·변경 등록, 추가는 `contractId === "new"`(위저드) */
export function ContractSheet({
  contractId,
  canManage,
  scope,
  onOpen,
  onClose,
}: {
  contractId: string;
  canManage: boolean;
  /** 상단에서 고른 과정·기수 (위저드에 미리 채운다) */
  scope: { bootcampId?: string; cohortId?: string };
  /** 추가한 계약을 같은 패널에서 연다 */
  onOpen: (id: string) => void;
  onClose: () => void;
}) {
  const isNew = contractId === "new";
  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined} className={isNew ? "w-160" : "w-140"}>
        {isNew ? (
          <ContractWizard scope={scope} onDone={(saved) => (saved ? onOpen(saved.id) : onClose())} />
        ) : (
          <ContractView contractId={contractId} canManage={canManage} onClose={onClose} />
        )}
      </SheetContent>
    </Sheet>
  );
}

/** 다음 단계 버튼 하나 (F96): 초안 [진행] · 진행 중 [계약 완료] · 종료일 없는 이행 중 [종료] */
function nextStep(c: Contract): { action: StepAction; label: string } | null {
  if (c.status === "DRAFT") return { action: "progress", label: "진행" };
  if (c.status === "IN_PROGRESS") return { action: "sign", label: "계약 완료" };
  if (c.status === "ACTIVE" && !c.end_date) return { action: "end", label: "종료" };
  return null;
}

function flowHint(c: Contract): string {
  switch (c.status) {
    case "DRAFT":
      return "계약서를 올리고 [진행]을 누르면 '진행 중'이 돼요.";
    case "IN_PROGRESS":
      return "서명을 마치면 [계약 완료]를 눌러요. 시작일이 오면 '이행 중'으로 바뀌어요.";
    case "SIGNED":
      return `시작일(${dotDate(c.start_date)})이 오면 자동으로 '이행 중'이 돼요.`;
    case "ACTIVE":
      return c.end_date
        ? `종료일(${dotDate(c.end_date)})이 지나면 자동으로 '종료'돼요.`
        : "종료일이 없어 [종료]를 눌러 끝내요.";
    case "ENDED":
      return "정상 종료된 계약이에요.";
    case "CANCELED":
      return "계약 완료 전에 취소한 계약이에요.";
    case "TERMINATED":
      return "계약 완료 뒤에 해지한 계약이에요.";
  }
}

type Dialog = "step" | "cancel" | "terminate" | "delete" | "manager" | "move" | null;

function ContractView({
  contractId,
  canManage,
  onClose,
}: {
  contractId: string;
  canManage: boolean;
  onClose: () => void;
}) {
  const contract = useQuery(contractQuery(contractId));
  const access = useQuery(staffAccessQuery);
  const canPickMentor = !!access.data && hasPermission(access.data, "educator.mentor.read");
  const [editing, setEditing] = useState<"edit" | "amend" | null>(null);
  const [dialog, setDialog] = useState<Dialog>(null);
  const c = contract.data;
  if (contract.isPending || contract.isError || !c)
    return (
      <>
        <PanelHead title="계약" description="" onClose={onClose} />
        {contract.isPending ? (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        ) : (
          <ErrorState className="m-6" onRetry={() => void contract.refetch()} />
        )}
      </>
    );
  if (editing) return <ContractEditForm contract={c} mode={editing} onDone={() => setEditing(null)} />;
  const status = STATUS[c.status];
  const beforeSign = c.status === "DRAFT" || c.status === "IN_PROGRESS";
  const signed = c.status === "SIGNED" || c.status === "ACTIVE";
  const step = canManage ? nextStep(c) : null;
  const menu = canManage && (beforeSign || signed);
  return (
    <>
      <PanelHead
        title={c.title}
        description={`${TYPE_LABELS[c.contract_type]} · ${academyText(c, true)} · ${c.contractor_name}`}
        badges={<Badge variant={status.badge}>{status.label}</Badge>}
        actions={
          canManage && (beforeSign || signed) ? (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditing(beforeSign ? "edit" : "amend")}>
                {beforeSign ? "수정" : "변경 등록"}
              </Button>
              {menu ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm" aria-label="더보기" className="px-2">
                      <Ellipsis />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent className="min-w-36">
                    {beforeSign ? <DropdownMenuItem onSelect={() => setDialog("cancel")}>취소</DropdownMenuItem> : null}
                    {signed ? <DropdownMenuItem onSelect={() => setDialog("terminate")}>해지</DropdownMenuItem> : null}
                    {c.status === "DRAFT" ? (
                      <DropdownMenuItem className="text-destructive-text" onSelect={() => setDialog("delete")}>
                        삭제
                      </DropdownMenuItem>
                    ) : null}
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : null}
            </div>
          ) : null
        }
        onClose={onClose}
      />
      <div className="flex flex-col gap-2 border-b border-border bg-card px-6 py-4">
        <div className="flex items-center gap-3">
          <StatusFlow contract={c} />
          {step ? (
            <Button size="sm" onClick={() => setDialog("step")}>
              {step.label}
            </Button>
          ) : null}
        </div>
        <p className="text-caption text-muted-foreground">{flowHint(c)}</p>
      </div>
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
        <PanelSection title="계약 정보">
          <PanelRow label="종류">{TYPE_LABELS[c.contract_type]}</PanelRow>
          <PanelRow label="과정 / 기수">{academyText(c, true)}</PanelRow>
          <PanelRow label="기간">{period(c)}</PanelRow>
          <PanelRow label="등록">{c.created_at ? formatKst(c.created_at, "yyyy.MM.dd") : "—"}</PanelRow>
        </PanelSection>
        <AmountView contract={c} />
        <PartyView
          contract={c}
          canMove={canManage && canPickMentor && c.contract_type === "MENTOR"}
          onMove={() => setDialog("move")}
        />
        <PanelSection title="계약서 · 담당">
          <PanelRow label="계약서">
            <FileRow contract={c} />
          </PanelRow>
          <PanelRow label="담당 직원">
            <div className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate">{c.manager_name ?? "—"}</span>
              {canManage ? (
                <Button variant="outline" size="sm" onClick={() => setDialog("manager")}>
                  변경
                </Button>
              ) : null}
            </div>
          </PanelRow>
        </PanelSection>
        {c.status === "CANCELED" ? (
          <PanelSection title="취소">
            <PanelRow label="취소 일자">{dotDate(c.canceled_on)}</PanelRow>
            <PanelRow label="사유" top>
              <span className="font-normal whitespace-pre-line">{c.cancel_reason ?? "—"}</span>
            </PanelRow>
          </PanelSection>
        ) : null}
        {c.status === "TERMINATED" ? (
          <PanelSection title="해지">
            <PanelRow label="해지 일자">{dotDate(c.terminated_on)}</PanelRow>
            <PanelRow label="사유">{c.termination_reason ? TERMINATION_LABELS[c.termination_reason] : "—"}</PanelRow>
            {c.termination_detail ? (
              <PanelRow label="상세" top>
                <span className="font-normal whitespace-pre-line">{c.termination_detail}</span>
              </PanelRow>
            ) : null}
          </PanelSection>
        ) : null}
        <AmendmentsView contract={c} />
      </div>
      {dialog === "step" && step ? (
        <StepDialog contract={c} action={step.action} onClose={() => setDialog(null)} />
      ) : null}
      {dialog === "cancel" ? <CancelDialog contract={c} onClose={() => setDialog(null)} /> : null}
      {dialog === "terminate" ? <TerminateDialog contract={c} onClose={() => setDialog(null)} /> : null}
      {dialog === "delete" ? <DeleteDialog contract={c} onCancel={() => setDialog(null)} onDeleted={onClose} /> : null}
      {dialog === "manager" ? <ManagerDialog contract={c} onClose={() => setDialog(null)} /> : null}
      {dialog === "move" ? <MoveDialog contract={c} onClose={() => setDialog(null)} /> : null}
    </>
  );
}

/** 상태 단계 (F96): 초안 → 진행 중 → 계약 완료 → 이행 중 → 종료. 취소·해지면 그 자리에서 끝난 표시 */
function StatusFlow({ contract: c }: { contract: Contract }) {
  const stopped = c.status === "CANCELED" || c.status === "TERMINATED";
  // 마지막으로 거친 단계: 취소는 초안·진행 중(계약서가 있으면 진행 중), 해지는 계약 완료·이행 중
  const reached = stopped
    ? c.status === "CANCELED"
      ? c.contract_file
        ? 1
        : 0
      : c.start_date && c.terminated_on && c.terminated_on >= c.start_date
        ? 3
        : 2
    : FLOW.indexOf(c.status);
  const ended = c.status === "ENDED";
  return (
    <ol aria-label="계약 단계" className="flex flex-1 items-center gap-1">
      {FLOW.map((s, i) => {
        const done = ended || i < reached || (stopped && i === reached);
        const current = !stopped && !ended && i === reached;
        const stopHere = stopped && i === reached + 1;
        const label = stopHere ? STATUS[c.status].label : STATUS[s].label;
        return (
          <li
            key={s}
            aria-current={current ? "step" : undefined}
            className="flex flex-1 flex-col items-center gap-1 text-center"
          >
            <span
              className={cn(
                "flex size-5 items-center justify-center rounded-full text-caption-strong",
                done || current
                  ? "bg-primary text-primary-foreground"
                  : stopHere
                    ? "bg-destructive-subtle text-destructive-text"
                    : "bg-muted text-muted-foreground",
                current && "ring-4 ring-primary/20",
              )}
            >
              {done ? <Check aria-hidden className="size-3" /> : stopHere ? "×" : null}
            </span>
            <span
              className={cn(
                "text-caption",
                current
                  ? "text-caption-strong text-primary-text"
                  : stopHere
                    ? "text-destructive-text"
                    : "text-muted-foreground",
              )}
            >
              {label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function AmountView({ contract: c }: { contract: Contract }) {
  return (
    <PanelSection title="금액">
      <PanelRow label="정산">
        {SETTLEMENT_LABELS[c.settlement_type]}
        {c.settlement_type === "UNIT_PRICE" && c.price_unit && c.unit_price != null
          ? ` · ${PRICE_UNIT_LABELS[c.price_unit]} ${won(c.unit_price)}`
          : c.settlement_type !== "UNIT_PRICE"
            ? ` · ${amountText(c)}`
            : ""}
      </PanelRow>
      {c.settlement_type === "UNIT_PRICE" && c.total_amount != null ? (
        <PanelRow label="예상 총액">{won(c.total_amount)}</PanelRow>
      ) : null}
      {c.contract_type === "MENTOR" ? (
        <>
          <PanelRow label="노쇼">{c.no_show_pay_amount != null ? `1건 ${won(c.no_show_pay_amount)}` : "—"}</PanelRow>
          <PanelRow label="정산 시간">
            {c.mentoring_time_basis ? TIME_BASIS_LABELS[c.mentoring_time_basis] : "—"}
          </PanelRow>
        </>
      ) : null}
      <PanelRow label="부가세">{VAT_LABELS[c.vat_type].replace("부가세 ", "")}</PanelRow>
      {c.amount_note ? (
        <PanelRow label="메모" top>
          <span className="font-normal whitespace-pre-line">{c.amount_note}</span>
        </PanelRow>
      ) : null}
    </PanelSection>
  );
}

function PartyView({ contract: c, canMove, onMove }: { contract: Contract; canMove: boolean; onMove: () => void }) {
  const vendor = isVendor(c.contract_type);
  const linked = linkedText(c);
  return (
    <PanelSection title="이름 또는 업체명">
      {c.contract_type === "MENTOR" ? (
        <PanelRow label="멘토" help={MENTOR_HELP}>
          <div className="flex items-center gap-2">
            <span className="min-w-0 flex-1 truncate">{linked.text}</span>
            {c.mentor_id ? (
              <Button variant="outline" size="sm" asChild>
                <Link
                  to="/admin/educators/mentors/$mentorId"
                  params={{ mentorId: c.mentor_id }}
                  search={{ tab: "contracts" }}
                >
                  멘토 보기
                </Link>
              </Button>
            ) : null}
            {canMove && c.mentor_id ? (
              <Button variant="outline" size="sm" onClick={onMove}>
                다른 멘토로 옮기기
              </Button>
            ) : null}
          </div>
        </PanelRow>
      ) : null}
      <PanelRow label={vendor ? "업체명" : "이름"}>{c.contractor_name}</PanelRow>
      <PanelRow label={vendor ? "전화" : "휴대폰"}>
        {c.contractor_phone
          ? vendor
            ? c.contractor_phone
            : (maskPhone(c.contractor_phone) ?? c.contractor_phone)
          : "—"}
      </PanelRow>
      <PanelRow label="이메일">{c.contractor_email ?? "—"}</PanelRow>
      {vendor ? (
        <>
          <PanelRow label="사업자번호">{c.business_registration_number ?? "—"}</PanelRow>
          <PanelRow label="담당자">{c.contact_person_name ?? "—"}</PanelRow>
        </>
      ) : null}
      {c.contract_type === "INSTRUCTOR" ? (
        <PanelRow label="강사" help="강사 연결은 강사 화면을 만들 때 더해요.">
          <span className={linked.muted ? "font-normal text-muted-foreground" : ""}>{linked.text}</span>
        </PanelRow>
      ) : null}
    </PanelSection>
  );
}

function useOpenUrl() {
  const [opening, setOpening] = useState(false);
  const open = async (get: () => Promise<string>) => {
    setOpening(true);
    try {
      window.open(await get(), "_blank", "noopener,noreferrer");
    } catch {
      toast.error("계약서를 열지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setOpening(false);
    }
  };
  return { opening, open };
}

function FileRow({ contract: c }: { contract: Contract }) {
  const { opening, open } = useOpenUrl();
  if (!c.contract_file)
    return <p className="text-body font-normal text-muted-foreground">없음 · 진행하려면 계약서가 필요해요</p>;
  const file = c.contract_file;
  return (
    <div className="flex items-center gap-3">
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-body-strong text-foreground">{file.file_name}</span>
        <span className="text-caption font-normal text-muted-foreground">
          {fileSize(file.file_size)}
          {file.created_at ? ` · ${formatKst(file.created_at, "yyyy.MM.dd")} 올림` : ""}
        </span>
      </div>
      <Button variant="outline" size="sm" disabled={opening} onClick={() => void open(() => contractFileUrl(c.id))}>
        보기
      </Button>
    </div>
  );
}

/** 변경 이력 (A109⑨): 일자 · 바뀐 항목 전 → 후 · 사유 · 등록자 · 변경 계약서 */
function AmendmentsView({ contract: c }: { contract: Contract }) {
  const list = useQuery(amendmentsQuery(c.id));
  const items = list.data ?? [];
  if (list.isPending || items.length === 0) return null;
  return (
    <PanelSection title={`변경 이력 · ${items.length}건`}>
      <ul aria-label="변경 이력" className="flex flex-col divide-y divide-border">
        {items.map((a) => (
          <AmendmentItem key={a.id} contractId={c.id} amendment={a} />
        ))}
      </ul>
    </PanelSection>
  );
}

function AmendmentItem({ contractId, amendment: a }: { contractId: string; amendment: Amendment }) {
  const { opening, open } = useOpenUrl();
  const keys = Object.keys(a.after ?? {});
  return (
    <li className="flex flex-col gap-1.5 py-2.5 first:pt-0 last:pb-0">
      <div className="flex items-center gap-2">
        <span className="text-body-strong text-foreground">{dotDate(a.amended_on)}</span>
        <span className="text-caption text-muted-foreground">등록 {a.created_by_name ?? "—"}</span>
        <div className="flex-1" />
        {a.contract_file ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={opening}
            onClick={() => void open(() => amendmentFileUrl(contractId, a.id))}
          >
            변경 계약서 보기
          </Button>
        ) : null}
      </div>
      <ul className="flex flex-col gap-0.5">
        {keys.map((k) => (
          <li key={k} className="text-body text-foreground">
            <span className="text-muted-foreground">{FIELD_LABELS[k] ?? k}</span>{" "}
            {fieldValue(k, (a.before as Record<string, unknown>)[k])} →{" "}
            {fieldValue(k, (a.after as Record<string, unknown>)[k])}
          </li>
        ))}
      </ul>
      <p className="text-caption whitespace-pre-line text-muted-foreground">사유: {a.reason}</p>
    </li>
  );
}
