import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm, type Control } from "react-hook-form";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { PanelActions, PanelHead, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { formatKst } from "@/lib/datetime";

import { useDeleteBlockTime, useSaveBlockTime, type BlockTime } from "../api";
import {
  BLOCK_END_TIMES,
  blockBody,
  blockForm,
  blockLabel,
  blockSchema,
  REASON_MAX_LENGTH,
  START_TIMES,
  type BlockForm,
} from "../form";

export type BlockSheetState = { mode: "view"; block: BlockTime } | { mode: "edit"; block: BlockTime } | { mode: "add" };

const HELP = {
  period: "이 기간의 평일(월~금)에만 적용돼요. 주말·공휴일은 빼요.",
  time: "이 시간에는 수강생이 신청할 수 없어요. 등록 전 신청·세션은 그대로예요.",
};

const ERROR_MESSAGES: Record<string, string> = {
  block_time_overlap: "같은 기간·시간대에 이미 금지 시간대가 있어요.",
  invalid_block_period: "시작 날짜가 끝 날짜보다 늦어요.",
  invalid_block_time: "시작 시각은 끝 시각보다 빨라야 해요.",
  invalid_block_reason: `사유는 ${REASON_MAX_LENGTH}자까지 적을 수 있어요.`,
  block_time_not_found: "이미 지워진 금지 시간대예요. 화면을 새로 불러와 주세요.",
};

function day(key: string): string {
  return formatKst(new Date(`${key}T00:00:00+09:00`), "yyyy.MM.dd");
}

/** 금지 시간대 패널 (Figma `멘토링 설정 · 금지 시간대 패널 (FE-19a)`, F68·F90·A34) */
export function BlockTimeSheet({
  cohortId,
  cohortTitle,
  state,
  canManage,
  onChange,
}: {
  cohortId: string;
  cohortTitle: string;
  state: BlockSheetState | null;
  canManage: boolean;
  onChange: (state: BlockSheetState | null) => void;
}) {
  const close = () => onChange(null);
  const [deleting, setDeleting] = useState<BlockTime | null>(null);
  return (
    <>
      <Sheet open={!!state} onOpenChange={(open) => (open ? undefined : close())}>
        <SheetContent aria-describedby={undefined} className="w-120">
          {state?.mode === "view" ? (
            <>
              <PanelHead
                title="금지 시간대"
                description={cohortTitle}
                actions={
                  canManage ? (
                    <PanelActions
                      onEdit={() => onChange({ mode: "edit", block: state.block })}
                      onDelete={() => setDeleting(state.block)}
                    />
                  ) : null
                }
                onClose={close}
              />
              <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
                <PanelSection title="적용">
                  <PanelRow label="기간" help={HELP.period}>
                    {day(state.block.period_start)} ~ {day(state.block.period_end)}
                  </PanelRow>
                  <PanelRow label="시간" help={HELP.time}>
                    {state.block.start_time.slice(0, 5)} ~ {state.block.end_time.slice(0, 5)}
                  </PanelRow>
                </PanelSection>
                <PanelSection title="기타">
                  <PanelRow label="사유">{state.block.reason ?? "—"}</PanelRow>
                </PanelSection>
              </div>
            </>
          ) : state ? (
            <BlockEditor
              key={state.mode === "edit" ? state.block.id : "add"}
              cohortId={cohortId}
              cohortTitle={cohortTitle}
              block={state.mode === "edit" ? state.block : null}
              onCancel={() => (state.mode === "edit" ? onChange({ mode: "view", block: state.block }) : close())}
              onSaved={(saved) => onChange({ mode: "view", block: saved })}
              onClose={close}
            />
          ) : null}
        </SheetContent>
      </Sheet>
      <DeleteDialog
        cohortId={cohortId}
        block={deleting}
        onClose={() => setDeleting(null)}
        onDeleted={() => {
          setDeleting(null);
          close();
        }}
      />
    </>
  );
}

function TimeSelect({
  control,
  name,
  label,
  options,
}: {
  control: Control<BlockForm>;
  name: "startTime" | "endTime";
  label: string;
  options: string[];
}) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <Select value={field.value} onValueChange={field.onChange}>
          <SelectTrigger aria-label={label} className="w-28 font-normal">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {options.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
    />
  );
}

function FieldError({ message }: { message?: string }) {
  return message ? <p className="mt-1 text-caption font-normal text-destructive-text">{message}</p> : null;
}

function BlockEditor({
  cohortId,
  cohortTitle,
  block,
  onCancel,
  onSaved,
  onClose,
}: {
  cohortId: string;
  cohortTitle: string;
  block: BlockTime | null;
  onCancel: () => void;
  onSaved: (saved: BlockTime) => void;
  onClose: () => void;
}) {
  const save = useSaveBlockTime(cohortId, block?.id ?? null);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<BlockForm>({ resolver: zodResolver(blockSchema), defaultValues: blockForm(block) });
  const errors = form.formState.errors;
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      const saved = await save.mutateAsync(blockBody(v));
      toast.success(block ? "금지 시간대를 고쳤어요" : "금지 시간대를 추가했어요");
      onSaved(saved);
    } catch (e) {
      const code = e instanceof ApiError ? e.code : undefined;
      setError((code && ERROR_MESSAGES[code]) ?? "저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  });
  return (
    <>
      <PanelHead
        title={block ? "금지 시간대" : "금지 시간대 추가"}
        description={cohortTitle}
        badges={block ? <Badge variant="warning">수정 중</Badge> : null}
        onClose={onClose}
      />
      <form
        aria-label={block ? "금지 시간대 수정" : "금지 시간대 추가"}
        noValidate
        onSubmit={(e) => void onSubmit(e)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
          <PanelSection title="적용">
            <PanelRow label="기간" help={HELP.period}>
              <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 font-normal">
                <Input type="date" aria-label="시작 날짜" {...form.register("periodStart")} />
                <span aria-hidden className="text-muted-foreground">
                  ~
                </span>
                <Input type="date" aria-label="끝 날짜" {...form.register("periodEnd")} />
              </div>
              <FieldError message={errors.periodStart?.message ?? errors.periodEnd?.message} />
            </PanelRow>
            <PanelRow label="시간" help={HELP.time}>
              <div className="flex items-center gap-2">
                <TimeSelect control={form.control} name="startTime" label="시작 시각" options={START_TIMES} />
                <span aria-hidden className="text-muted-foreground">
                  ~
                </span>
                <TimeSelect control={form.control} name="endTime" label="끝 시각" options={BLOCK_END_TIMES} />
              </div>
              <FieldError message={errors.endTime?.message} />
            </PanelRow>
          </PanelSection>
          <PanelSection title="기타">
            <PanelRow label="사유" htmlFor="block-reason">
              <Input
                id="block-reason"
                maxLength={REASON_MAX_LENGTH}
                placeholder="예: 정규 수업"
                className="font-normal"
                {...form.register("reason")}
              />
              <FieldError message={errors.reason?.message} />
            </PanelRow>
          </PanelSection>
          {error ? <Alert variant="error" title={error} /> : null}
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-6 py-3">
          <Button type="button" variant="outline" onClick={onCancel}>
            취소
          </Button>
          <Button type="submit" disabled={save.isPending}>
            저장
          </Button>
        </div>
      </form>
    </>
  );
}

function DeleteDialog({
  cohortId,
  block,
  onClose,
  onDeleted,
}: {
  cohortId: string;
  block: BlockTime | null;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const remove = useDeleteBlockTime(cohortId);
  const [error, setError] = useState<string | null>(null);
  const onDelete = async () => {
    if (!block) return;
    setError(null);
    try {
      await remove.mutateAsync(block.id);
      toast.success("금지 시간대를 지웠어요");
      onDeleted();
    } catch (e) {
      const code = e instanceof ApiError ? e.code : undefined;
      setError((code && ERROR_MESSAGES[code]) ?? "지우지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  };
  return (
    <Dialog
      open={!!block}
      onOpenChange={(open) => {
        if (!open) {
          setError(null);
          onClose();
        }
      }}
    >
      <DialogContent className="flex max-w-110 flex-col gap-4 p-6">
        <DialogTitle className="text-h2 text-foreground">이 금지 시간대를 지울까요?</DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          {block ? blockLabel(block) : ""}
          <br />
          지우면 이 시간에도 수강생이 신청할 수 있어요.
        </DialogDescription>
        {error ? <Alert variant="error" title={error} /> : null}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            돌아가기
          </Button>
          <Button variant="destructive" disabled={remove.isPending} onClick={() => void onDelete()}>
            지우기
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
