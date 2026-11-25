import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useId, useState } from "react";
import { toast } from "sonner";

import { ErrorState } from "@/components/error-state";
import { PanelActions, PanelHead, PanelList, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { DiscardDialog } from "@/features/admin-org/components/shared";
import { errorText } from "@/features/admin-org/text";
import { hasPermission, type StaffAccess } from "@/features/staff/api";

import { hrdCohortsQuery, useSaveHrdCohort, type HrdBootcamp, type HrdCohort } from "../api";
import { optionalPeriod, won } from "../labels";

/** HRD 회차 패널 (F75): 회차·기간·연결 기수는 조회만, 자부담금만 수정 */
export function HrdCohortSheet({
  hrd,
  cohortId,
  access,
  onClose,
}: {
  hrd: HrdBootcamp;
  cohortId: string;
  access: StaffAccess;
  onClose: () => void;
}) {
  const cohorts = useQuery(hrdCohortsQuery(hrd.id));
  const c = cohorts.data?.find((x) => x.id === cohortId);
  const canManage = hasPermission(access, "academy.hrd.manage");
  const [editing, setEditing] = useState(false);
  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined}>
        <PanelHead
          title={c ? `${c.cohort_number}회차` : "회차"}
          description={`${hrd.name} · 회차`}
          badges={editing ? <Badge variant="info">수정 중</Badge> : null}
          actions={c && canManage && !editing ? <PanelActions onEdit={() => setEditing(true)} /> : null}
          onClose={onClose}
        />
        {cohorts.isPending ? (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        ) : cohorts.isError || !c ? (
          <ErrorState className="m-6" onRetry={() => void cohorts.refetch()} />
        ) : editing ? (
          <SelfPayForm cohort={c} hrd={hrd} onDone={() => setEditing(false)} />
        ) : (
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
            <BasicSection cohort={c} />
            <PanelSection title="비용">
              <PanelRow label="자부담금">{won(c.self_pay_amount)}</PanelRow>
            </PanelSection>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function BasicSection({ cohort: c }: { cohort: HrdCohort }) {
  return (
    <PanelSection title="기본 정보">
      <PanelRow label="회차">{c.cohort_number}회차</PanelRow>
      <PanelRow label="훈련 기간">{optionalPeriod(c.train_start_date, c.train_end_date)}</PanelRow>
      <PanelRow label="연결 기수" top={(c.linked_cohorts ?? []).length > 0}>
        {(c.linked_cohorts ?? []).length ? (
          <PanelList
            label="연결 기수"
            items={(c.linked_cohorts ?? []).map((l) => ({ id: l.id, name: `${l.bootcamp_name} ${l.cohort_number}기` }))}
          />
        ) : (
          "없음"
        )}
      </PanelRow>
    </PanelSection>
  );
}

function SelfPayForm({ cohort: c, hrd, onDone }: { cohort: HrdCohort; hrd: HrdBootcamp; onDone: () => void }) {
  const id = useId();
  const initial = c.self_pay_amount === null || c.self_pay_amount === undefined ? "" : String(c.self_pay_amount);
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const save = useSaveHrdCohort(c);
  const valid = /^\d{0,10}$/.test(value.trim());
  const dirty = value.trim() !== initial;
  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !save.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });
  const onSubmit = async () => {
    setError(null);
    try {
      await save.mutateAsync(value.trim() ? Number(value.trim()) : null);
      toast.success(`${hrd.name} ${c.cohort_number}회차를 저장했어요`);
      onDone();
    } catch (e) {
      setError(errorText(e));
    }
  };
  return (
    <form
      aria-label="회차 수정"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) void onSubmit();
      }}
      className="flex min-h-0 flex-1 flex-col"
    >
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
        <BasicSection cohort={c} />
        <PanelSection title="비용">
          <PanelRow label="자부담금" htmlFor={`${id}-pay`}>
            <span className="flex items-center gap-2 font-normal">
              <Input
                id={`${id}-pay`}
                inputMode="numeric"
                aria-invalid={!valid}
                className="font-normal"
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
              <span className="shrink-0 text-body text-muted-foreground">원</span>
            </span>
            {!valid ? (
              <p className="mt-1 text-caption font-normal text-destructive-text">0 이상의 숫자만 적어 주세요.</p>
            ) : null}
          </PanelRow>
        </PanelSection>
        {error ? <Alert variant="error" title={error} /> : null}
      </div>
      <div className="flex justify-end gap-2 border-t border-border px-6 py-3">
        <Button type="button" variant="outline" onClick={onDone}>
          취소
        </Button>
        <Button type="submit" disabled={save.isPending || !valid || !dirty}>
          저장
        </Button>
      </div>
      <DiscardDialog blocker={blocker} />
    </form>
  );
}
