import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";

import {
  mentorAssignmentsQuery,
  useActivate,
  useDeactivate,
  useReactivate,
  type Deactivation,
  type MentorItem,
} from "../api";

const FAILED = "처리하지 못했어요. 잠시 후 다시 시도해 주세요.";

/**
 * 머리의 [비활성화]/[활성화] (A35·F79).
 * 비활성화: 미리보기(함께 꺼질 배정·취소될 대기 신청)를 확인 창에 보여 주고 확인하면 적용.
 * 활성화: 확인 후 적용하고, 멘토 비활성화로 꺼졌던 배정이 있으면 다시 켤 배정을 고르는 창.
 */
export function ActivationActions({ mentor }: { mentor: MentorItem }) {
  // 가입 전 멘토(A104)는 활성화할 수 없다
  if (!mentor.is_registered) return null;
  return mentor.is_active ? <Deactivate mentor={mentor} /> : <Activate mentor={mentor} />;
}

/** 배정 id → "백엔드 부트캠프 12기" (배정 응답에는 기수 이름이 없어 멘토 배정 목록에서 찾는다) */
function useCohortNames(mentorId: string) {
  const list = useQuery(mentorAssignmentsQuery(mentorId));
  return (id: string) => {
    const a = list.data?.find((x) => x.id === id);
    return a ? `${a.bootcamp_name} ${a.cohort_number}기` : "기수 배정";
  };
}

function Deactivate({ mentor }: { mentor: MentorItem }) {
  const run = useDeactivate(mentor.id);
  const nameOf = useCohortNames(mentor.id);
  const [preview, setPreview] = useState<Deactivation | null>(null);
  const open = async () => {
    try {
      setPreview(await run.mutateAsync(false));
    } catch {
      toast.error(FAILED);
    }
  };
  const confirm = async () => {
    try {
      const res = await run.mutateAsync(true);
      setPreview(null);
      toast.success(
        res.pending_requests > 0
          ? `멘토를 비활성화했어요. 대기 중인 신청 ${res.pending_requests}건을 취소했어요`
          : "멘토를 비활성화했어요",
      );
    } catch {
      toast.error(FAILED);
    }
  };
  return (
    <>
      <Button variant="outline" disabled={run.isPending} onClick={() => void open()}>
        {run.isPending && !preview ? <Spinner className="size-4" /> : null}
        비활성화
      </Button>
      <Dialog open={!!preview} onOpenChange={(o) => (o ? undefined : setPreview(null))}>
        <DialogContent className="flex max-w-120 flex-col gap-4 p-6">
          <DialogTitle className="text-h2 text-foreground">{mentor.name} 멘토를 비활성화할까요?</DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            신청 받기와 활성 배정이 모두 꺼지고 대기 중인 신청은 취소돼요. 이미 승인한 세션은 그대로예요. 로그인은 막지
            않아요.
          </DialogDescription>
          {preview && preview.assignments.length > 0 ? (
            <section aria-labelledby="off-title" className="flex flex-col gap-2">
              <h3 id="off-title" className="text-label text-foreground">
                함께 꺼지는 배정 {preview.assignments.length}개
              </h3>
              <ul className="flex flex-col divide-y divide-border rounded-md border border-border">
                {preview.assignments.map((a) => (
                  <li key={a.id} className="px-3 py-2 text-body text-foreground">
                    {nameOf(a.id)}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          {preview && preview.pending_requests > 0 ? (
            <p className="text-body text-foreground">
              대기 중인 신청 {preview.pending_requests}건은 자동으로 취소돼요.
            </p>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setPreview(null)}>
              돌아가기
            </Button>
            <Button variant="destructive" disabled={run.isPending} onClick={() => void confirm()}>
              비활성화
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function Activate({ mentor }: { mentor: MentorItem }) {
  const run = useActivate(mentor.id);
  const reactivate = useReactivate(mentor.id);
  const nameOf = useCohortNames(mentor.id);
  const [confirming, setConfirming] = useState(false);
  const [restorable, setRestorable] = useState<string[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const activate = async () => {
    try {
      const res = await run.mutateAsync();
      setConfirming(false);
      toast.success("멘토를 활성화했어요");
      const ids = res.restorable.map((a) => a.id);
      setRestorable(ids);
      setPicked(ids);
    } catch {
      toast.error(FAILED);
    }
  };
  const restore = async () => {
    try {
      const res = await reactivate.mutateAsync(picked);
      setRestorable([]);
      if (res.failed.length > 0)
        toast.error(`${res.reactivated.length}개를 다시 켰어요. ${res.failed.length}개는 켜지 못했어요`);
      else toast.success(`배정 ${res.reactivated.length}개를 다시 켰어요`);
    } catch {
      toast.error(FAILED);
    }
  };
  return (
    <>
      <Button onClick={() => setConfirming(true)}>활성화</Button>
      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent className="flex max-w-110 flex-col gap-4 p-6">
          <DialogTitle className="text-h2 text-foreground">{mentor.name} 멘토를 활성화할까요?</DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            새 배정과 신청 받기를 다시 할 수 있어요. 꺼진 배정은 다음 창에서 골라 다시 켤 수 있어요.
          </DialogDescription>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              돌아가기
            </Button>
            <Button disabled={run.isPending} onClick={() => void activate()}>
              활성화
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={restorable.length > 0} onOpenChange={(o) => (o ? undefined : setRestorable([]))}>
        <DialogContent className="flex max-w-120 flex-col gap-4 p-6">
          <DialogTitle className="text-h2 text-foreground">배정을 다시 켤까요?</DialogTitle>
          <DialogDescription className="text-body text-muted-foreground">
            멘토를 비활성화할 때 함께 꺼진 배정이에요. 다시 켤 배정을 골라 주세요.
          </DialogDescription>
          <ul
            aria-label="다시 켤 배정"
            className="flex flex-col divide-y divide-border rounded-md border border-border"
          >
            {restorable.map((id) => (
              <li key={id}>
                <label className="flex items-center gap-3 px-3 py-2.5 text-body text-foreground">
                  <Checkbox
                    checked={picked.includes(id)}
                    onCheckedChange={(c) => setPicked((p) => (c === true ? [...p, id] : p.filter((x) => x !== id)))}
                  />
                  {nameOf(id)}
                </label>
              </li>
            ))}
          </ul>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setRestorable([])}>
              건너뛰기
            </Button>
            <Button disabled={picked.length === 0 || reactivate.isPending} onClick={() => void restore()}>
              다시 켜기
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
