import { useId, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { Textarea } from "@/components/ui/textarea";
import { kstDateKey } from "@/features/apply/slots";

import {
  useCancelContract,
  useDeleteContract,
  useStepContract,
  useTerminateContract,
  useUpdateContract,
  type Contract,
  type StepAction,
  type TerminationReason,
} from "../api";
import { contractError, TERMINATION_LABELS } from "../labels";
import { ManagerList, type ManagerChoice } from "./pickers";

const NOTE_MAX = 500;

function Frame({
  title,
  description,
  children,
  onClose,
}: {
  title: string;
  description: string;
  children: ReactNode;
  onClose: () => void;
}) {
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-120 flex-col gap-4 p-6">
        <DialogTitle className="text-h2 text-foreground">{title}</DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">{description}</DialogDescription>
        {children}
      </DialogContent>
    </Dialog>
  );
}

const STEP_TEXT: Record<StepAction, { title: string; body: string; button: string; done: string }> = {
  progress: {
    title: "계약을 진행할까요?",
    body: "'진행 중'이 되면 계약서가 꼭 있어야 하고, 서명을 마치면 [계약 완료]를 눌러요.",
    button: "진행",
    done: "계약을 진행 중으로 바꿨어요",
  },
  sign: {
    title: "계약 완료로 바꿀까요?",
    body: "서명을 마친 계약이에요. 시작일이 없거나 지났으면 바로 '이행 중'이 되고, 이후 내용은 변경 등록으로만 바꿔요.",
    button: "계약 완료",
    done: "계약 완료로 바꿨어요",
  },
  end: {
    title: "계약을 종료할까요?",
    body: "종료일이 없는 계약을 정상 종료해요. 이 계약을 근거로 한 기수 배정도 함께 끝나요.",
    button: "종료",
    done: "계약을 종료했어요",
  },
};

/** 다음 단계 확인 창 (A109③) */
export function StepDialog({
  contract: c,
  action,
  onClose,
}: {
  contract: Contract;
  action: StepAction;
  onClose: () => void;
}) {
  const run = useStepContract(c.id);
  const text = STEP_TEXT[action];
  const submit = async () => {
    try {
      await run.mutateAsync(action);
      toast.success(text.done);
      onClose();
    } catch (e) {
      toast.error(contractError(e));
    }
  };
  return (
    <Frame title={text.title} description={text.body} onClose={onClose}>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          돌아가기
        </Button>
        <Button disabled={run.isPending} onClick={() => void submit()}>
          {text.button}
        </Button>
      </div>
    </Frame>
  );
}

/** 취소 (초안·진행 중, A109③): 사유 500자 필수 · 일자(비우면 오늘) */
export function CancelDialog({ contract: c, onClose }: { contract: Contract; onClose: () => void }) {
  const id = useId();
  const cancel = useCancelContract(c.id);
  const [reason, setReason] = useState("");
  const [on, setOn] = useState(() => kstDateKey(new Date()));
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    if (!reason.trim()) {
      setError("취소 사유를 적어 주세요.");
      return;
    }
    try {
      await cancel.mutateAsync({ reason: reason.trim(), canceled_on: on || null });
      toast.success("계약을 취소했어요");
      onClose();
    } catch (e) {
      setError(contractError(e));
    }
  };
  return (
    <Frame
      title="계약을 취소할까요?"
      description="계약 완료 전에 그만두는 계약이에요. 취소한 계약은 되돌릴 수 없어요."
      onClose={onClose}
    >
      <label htmlFor={`${id}-reason`} className="text-body-strong text-foreground">
        취소 사유
      </label>
      <Textarea
        id={`${id}-reason`}
        rows={3}
        maxLength={NOTE_MAX}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      <label htmlFor={`${id}-on`} className="text-body-strong text-foreground">
        취소 일자
      </label>
      <Input id={`${id}-on`} type="date" className="w-44" value={on} onChange={(e) => setOn(e.target.value)} />
      {error ? <Alert variant="error" title={error} /> : null}
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          돌아가기
        </Button>
        <Button variant="destructive" disabled={cancel.isPending} onClick={() => void submit()}>
          취소하기
        </Button>
      </div>
    </Frame>
  );
}

const REASONS: TerminationReason[] = [
  "TERMINATED_BY_MUTUAL_AGREEMENT",
  "TERMINATED_BY_FAULT",
  "TERMINATED_BY_UNILATERAL",
];

const SHORT_REASON: Record<TerminationReason, string> = {
  TERMINATED_BY_MUTUAL_AGREEMENT: "합의",
  TERMINATED_BY_FAULT: "귀책 사유",
  TERMINATED_BY_UNILATERAL: "일방적",
};

/** 해지 (계약 완료·이행 중, A109③): 사유 3종 · 상세(선택) · 일자(비우면 오늘) */
export function TerminateDialog({ contract: c, onClose }: { contract: Contract; onClose: () => void }) {
  const id = useId();
  const terminate = useTerminateContract(c.id);
  const [reason, setReason] = useState<TerminationReason>("TERMINATED_BY_MUTUAL_AGREEMENT");
  const [detail, setDetail] = useState("");
  const [on, setOn] = useState(() => kstDateKey(new Date()));
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    try {
      await terminate.mutateAsync({ reason, detail: detail.trim() || null, terminated_on: on || null });
      toast.success("계약을 해지했어요");
      onClose();
    } catch (e) {
      setError(contractError(e));
    }
  };
  return (
    <Frame
      title="계약을 해지할까요?"
      description="계약 완료 뒤에 그만두는 계약이에요. 이 계약을 근거로 한 기수 배정도 함께 끝나요."
      onClose={onClose}
    >
      <span className="text-body-strong text-foreground">해지 사유</span>
      <Segmented
        label="해지 사유"
        value={reason}
        onChange={setReason}
        options={REASONS.map((r) => ({ value: r, label: SHORT_REASON[r] }))}
      />
      <p className="-mt-2 text-caption text-muted-foreground">{TERMINATION_LABELS[reason]}</p>
      <label htmlFor={`${id}-detail`} className="text-body-strong text-foreground">
        상세 (선택)
      </label>
      <Textarea
        id={`${id}-detail`}
        rows={3}
        maxLength={NOTE_MAX}
        value={detail}
        onChange={(e) => setDetail(e.target.value)}
      />
      <label htmlFor={`${id}-on`} className="text-body-strong text-foreground">
        해지 일자
      </label>
      <Input id={`${id}-on`} type="date" className="w-44" value={on} onChange={(e) => setOn(e.target.value)} />
      {error ? <Alert variant="error" title={error} /> : null}
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          돌아가기
        </Button>
        <Button variant="destructive" disabled={terminate.isPending} onClick={() => void submit()}>
          해지
        </Button>
      </div>
    </Frame>
  );
}

/** 삭제 (초안만) */
export function DeleteDialog({
  contract: c,
  onCancel,
  onDeleted,
}: {
  contract: Contract;
  onCancel: () => void;
  onDeleted: () => void;
}) {
  const remove = useDeleteContract(c.id);
  const submit = async () => {
    try {
      await remove.mutateAsync();
      toast.success("계약을 지웠어요");
      onDeleted();
    } catch (e) {
      toast.error(contractError(e));
    }
  };
  return (
    <Frame
      title="계약을 지울까요?"
      description="초안인 계약만 지울 수 있어요. 가입 전 멘토에 다른 계약이 없으면 그 멘토도 함께 지워져요."
      onClose={onCancel}
    >
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>
          돌아가기
        </Button>
        <Button variant="destructive" disabled={remove.isPending} onClick={() => void submit()}>
          삭제
        </Button>
      </div>
    </Frame>
  );
}

/** 담당 직원 변경 (상태와 무관, A111) */
export function ManagerDialog({ contract: c, onClose }: { contract: Contract; onClose: () => void }) {
  const update = useUpdateContract(c.id);
  const [choice, setChoice] = useState<ManagerChoice>({ id: c.manager_employee_id, name: c.manager_name ?? "—" });
  const submit = async () => {
    if (choice.id === c.manager_employee_id) {
      onClose();
      return;
    }
    try {
      await update.mutateAsync({ manager_employee_id: choice.id });
      toast.success(`담당 직원을 ${choice.name}(으)로 바꿨어요`);
      onClose();
    } catch (e) {
      toast.error(contractError(e));
    }
  };
  return (
    <Frame title="담당 직원 변경" description="계약을 진행하고 관리할 직원을 골라요." onClose={onClose}>
      <ManagerList value={choice} onChange={setChoice} />
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          돌아가기
        </Button>
        <Button disabled={update.isPending} onClick={() => void submit()}>
          변경
        </Button>
      </div>
    </Frame>
  );
}
