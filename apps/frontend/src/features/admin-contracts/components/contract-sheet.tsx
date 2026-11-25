import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorState } from "@/components/error-state";
import { PanelHead, PanelRow, PanelSection } from "@/components/panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { maskPhone } from "@/features/profile/mask";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { formatKst } from "@/lib/datetime";

import {
  contractFileUrl,
  contractQuery,
  useContractAction,
  useDeleteContract,
  type Contract,
  type ContractAction,
} from "../api";
import { contractError, fileSize, linkedText, period, STATUS, TYPE_LABELS } from "../labels";
import { ContractForm } from "./contract-form";
import { ManagerDialog, MoveDialog } from "./pickers";

/** 계약 패널 (F83): 조회·수정(작성 중)·확정·해지·삭제, 추가는 `contractId === "new"` */
export function ContractSheet({
  contractId,
  canManage,
  onOpen,
  onClose,
}: {
  contractId: string;
  canManage: boolean;
  /** 추가한 계약을 같은 패널에서 연다 */
  onOpen: (id: string) => void;
  onClose: () => void;
}) {
  const isNew = contractId === "new";
  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined} className="w-120">
        {isNew ? (
          <>
            <PanelHead
              title="계약 추가"
              description="저장하면 작성 중이에요. 확정은 저장한 뒤에 해요."
              onClose={onClose}
            />
            <ContractForm onDone={(saved) => (saved ? onOpen(saved.id) : onClose())} />
          </>
        ) : (
          <ContractView contractId={contractId} canManage={canManage} onClose={onClose} />
        )}
      </SheetContent>
    </Sheet>
  );
}

const ACTION_TEXT: Record<ContractAction | "delete", { title: string; body: string; button: string; done: string }> = {
  confirm: {
    title: "계약을 확정할까요?",
    body: "확정하면 담당 직원 말고는 고칠 수 없어요. 종료일이 지난 계약은 바로 종료로 확정돼요.",
    button: "확정",
    done: "계약을 확정했어요",
  },
  terminate: {
    title: "계약을 해지할까요?",
    body: "해지한 계약은 다시 되돌릴 수 없어요.",
    button: "해지",
    done: "계약을 해지했어요",
  },
  delete: {
    title: "계약을 지울까요?",
    body: "작성 중인 계약만 지울 수 있어요. 가입 전 멘토에 다른 계약이 없으면 그 멘토도 함께 지워져요.",
    button: "삭제",
    done: "계약을 지웠어요",
  },
};

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
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState<ContractAction | "delete" | null>(null);
  const [picker, setPicker] = useState<"manager" | "mentor" | null>(null);
  const c = contract.data;
  if (contract.isPending)
    return (
      <>
        <PanelHead title="계약" description="" onClose={onClose} />
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      </>
    );
  if (contract.isError || !c)
    return (
      <>
        <PanelHead title="계약" description="" onClose={onClose} />
        <ErrorState className="m-6" onRetry={() => void contract.refetch()} />
      </>
    );
  const status = STATUS[c.status];
  const head = (
    <PanelHead
      title={c.title}
      description={`${c.contractor_name} · ${TYPE_LABELS[c.educator_type]} 계약`}
      badges={<Badge variant={status.badge}>{status.label}</Badge>}
      onClose={onClose}
    />
  );
  if (editing)
    return (
      <>
        {head}
        <ContractForm contract={c} onDone={() => setEditing(false)} />
      </>
    );
  const draft = c.status === "DRAFT";
  return (
    <>
      {head}
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
        <PanelSection title="계약 정보">
          <PanelRow label="계약자">{c.contractor_name}</PanelRow>
          <PanelRow label="휴대폰">{maskPhone(c.contractor_phone) ?? c.contractor_phone}</PanelRow>
          <PanelRow label="이메일">{c.contractor_email ?? "—"}</PanelRow>
          <PanelRow label="기간">{period(c)}</PanelRow>
          <PanelRow label="등록">{c.created_at ? formatKst(c.created_at, "yyyy.MM.dd") : "—"}</PanelRow>
        </PanelSection>
        <PanelSection title="계약서">
          <FileRow contract={c} />
        </PanelSection>
        <PanelSection title={c.educator_type === "MENTOR" ? "멘토" : "강사"}>
          <LinkRow contract={c} canMove={canManage && canPickMentor} onMove={() => setPicker("mentor")} />
        </PanelSection>
        <PanelSection title="담당 직원">
          <div className="flex items-center gap-2">
            <span className="min-w-0 flex-1 truncate text-body-strong text-foreground">{c.manager_name ?? "—"}</span>
            {canManage ? (
              <Button variant="outline" size="sm" onClick={() => setPicker("manager")}>
                변경
              </Button>
            ) : null}
          </div>
        </PanelSection>
      </div>
      {canManage && (draft || c.status === "ACTIVE") ? (
        <div className="flex gap-2 border-t border-border px-6 py-3">
          {draft ? (
            <>
              <Button
                variant="outline"
                className="border-destructive-text text-destructive-text hover:bg-destructive-subtle hover:text-destructive-text"
                onClick={() => setConfirming("delete")}
              >
                삭제
              </Button>
              <span className="flex-1" />
              <Button variant="outline" onClick={() => setEditing(true)}>
                수정
              </Button>
              <Button onClick={() => setConfirming("confirm")}>확정</Button>
            </>
          ) : (
            <Button
              variant="outline"
              className="border-destructive-text text-destructive-text hover:bg-destructive-subtle hover:text-destructive-text"
              onClick={() => setConfirming("terminate")}
            >
              해지
            </Button>
          )}
        </div>
      ) : null}
      {confirming ? (
        <ActionDialog
          contract={c}
          action={confirming}
          onDone={(deleted) => (deleted ? onClose() : setConfirming(null))}
          onCancel={() => setConfirming(null)}
        />
      ) : null}
      {picker === "manager" ? <ManagerDialog contract={c} onClose={() => setPicker(null)} /> : null}
      {picker === "mentor" ? <MoveDialog contract={c} onClose={() => setPicker(null)} /> : null}
    </>
  );
}

function FileRow({ contract: c }: { contract: Contract }) {
  const [opening, setOpening] = useState(false);
  if (!c.contract_file) return <p className="text-body text-muted-foreground">없음 · 확정하려면 계약서가 필요해요</p>;
  const file = c.contract_file;
  const open = async () => {
    setOpening(true);
    try {
      window.open(await contractFileUrl(c.id), "_blank", "noopener,noreferrer");
    } catch {
      toast.error("계약서를 열지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setOpening(false);
    }
  };
  return (
    <div className="flex items-center gap-3">
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-body-strong text-foreground">{file.file_name}</span>
        <span className="text-caption text-muted-foreground">
          {fileSize(file.file_size)}
          {file.created_at ? ` · ${formatKst(file.created_at, "yyyy.MM.dd")} 올림` : ""}
        </span>
      </div>
      <Button variant="outline" size="sm" disabled={opening} onClick={() => void open()}>
        보기
      </Button>
    </div>
  );
}

function LinkRow({ contract: c, canMove, onMove }: { contract: Contract; canMove: boolean; onMove: () => void }) {
  const linked = linkedText(c);
  if (c.educator_type === "INSTRUCTOR")
    return (
      <p className="text-body text-muted-foreground">
        {linked.muted ? "연결된 강사가 없어요. 강사 연결은 강사 화면에서 할 수 있게 돼요." : linked.text}
      </p>
    );
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <span className="min-w-0 flex-1 truncate text-body-strong text-foreground">{linked.text}</span>
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
      <p className="text-caption text-muted-foreground">
        잘못 만든 계약은 다른 멘토로 옮길 수 있어요. 연결 해제는 없어요.
      </p>
    </div>
  );
}

function ActionDialog({
  contract: c,
  action,
  onDone,
  onCancel,
}: {
  contract: Contract;
  action: ContractAction | "delete";
  onDone: (deleted: boolean) => void;
  onCancel: () => void;
}) {
  const run = useContractAction(c.id);
  const remove = useDeleteContract(c.id);
  const text = ACTION_TEXT[action];
  const pending = run.isPending || remove.isPending;
  const submit = async () => {
    try {
      if (action === "delete") await remove.mutateAsync();
      else await run.mutateAsync(action);
      toast.success(text.done);
      onDone(action === "delete");
    } catch (e) {
      toast.error(contractError(e));
    }
  };
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onCancel())}>
      <DialogContent className="flex max-w-110 flex-col gap-4 p-6">
        <DialogTitle className="text-h2 text-foreground">{text.title}</DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">{text.body}</DialogDescription>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel}>
            돌아가기
          </Button>
          <Button
            variant={action === "confirm" ? "primary" : "destructive"}
            disabled={pending}
            onClick={() => void submit()}
          >
            {text.button}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
