import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ApiError } from "@/api/errors";
import { PanelActions, PanelHead, PanelList, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";

import { hasImpact, impactQuery, useDeleteDepartment, useSaveDepartment, type Department, type Team } from "../api";
import { ImpactList } from "./impact-list";
import { eul, errorText } from "../text";
import { DiscardDialog } from "./shared";

const schema = z.object({
  name: z.string().trim().min(1, "부서 이름을 적어 주세요.").max(20, "부서 이름은 20자까지예요."),
  description: z.string().trim().min(1, "설명을 적어 주세요.").max(500, "설명은 500자까지예요."),
  rules: z.string(),
});
type Values = z.infer<typeof schema>;

/** 부서 패널 (F68·F69). department가 null이면 추가 */
export function DepartmentSheet({
  department,
  teams,
  canManage,
  onClose,
}: {
  department: Department | null;
  teams: Team[];
  canManage: boolean;
  onClose: () => void;
}) {
  const [editing, setEditing] = useState(department === null);
  const [deleting, setDeleting] = useState(false);
  const title = department?.name ?? "새 부서";
  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined}>
        <PanelHead
          title={title}
          description="부서"
          badges={editing && department ? <Badge variant="info">수정 중</Badge> : null}
          actions={
            canManage && !editing ? (
              <PanelActions onEdit={() => setEditing(true)} onDelete={() => setDeleting(true)} />
            ) : null
          }
          onClose={onClose}
        />
        {editing ? (
          <DepartmentForm department={department} onDone={() => (department ? setEditing(false) : onClose())} />
        ) : department ? (
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
            <PanelSection title="기본 정보">
              <PanelRow label="이름">{department.name}</PanelRow>
              <PanelRow label="설명">
                <span className="whitespace-pre-line">{department.description}</span>
              </PanelRow>
              <PanelRow label="직원" help="팀이 없는 직원을 포함한 부서의 직원 수예요.">
                {department.employee_count}명
              </PanelRow>
            </PanelSection>
            <PanelSection title="규칙">
              {department.rules ? (
                <p className="text-body whitespace-pre-line text-foreground">{department.rules}</p>
              ) : (
                <p className="text-body text-muted-foreground">정한 규칙이 없어요.</p>
              )}
            </PanelSection>
            <PanelSection title="팀">
              {teams.length ? (
                <PanelList
                  label="팀"
                  items={teams.map((t) => ({ id: t.id, name: t.name, meta: `직원 ${t.employee_count}명` }))}
                />
              ) : (
                <p className="text-body text-muted-foreground">팀이 없어요.</p>
              )}
            </PanelSection>
          </div>
        ) : null}
        {deleting && department ? (
          <DeleteDepartmentDialog department={department} onClose={() => setDeleting(false)} onDeleted={onClose} />
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function DepartmentForm({ department, onDone }: { department: Department | null; onDone: () => void }) {
  const id = useId();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: department?.name ?? "",
      description: department?.description ?? "",
      rules: department?.rules ?? "",
    },
  });
  const save = useSaveDepartment(department?.id ?? null);
  const [error, setError] = useState<string | null>(null);
  const dirty = form.formState.isDirty;
  const blocker = useBlocker({
    shouldBlockFn: () => dirty && !save.isPending,
    enableBeforeUnload: () => dirty,
    withResolver: true,
  });
  const { errors } = form.formState;

  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await save.mutateAsync({ name: v.name, description: v.description, rules: v.rules.trim() || null });
      form.reset(v);
      toast.success(department ? `${v.name} 부서를 저장했어요` : `${v.name} 부서를 만들었어요`);
      onDone();
    } catch (e) {
      if (e instanceof ApiError && e.code === "department_name_taken")
        form.setError("name", { message: "같은 이름의 부서가 있어요." });
      else setError(errorText(e));
    }
  });

  return (
    <form
      aria-label={department ? "부서 수정" : "부서 추가"}
      noValidate
      onSubmit={(e) => void onSubmit(e)}
      className="flex min-h-0 flex-1 flex-col"
    >
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
        <PanelSection title="기본 정보">
          <PanelRow label="이름" htmlFor={`${id}-name`}>
            <Input id={`${id}-name`} maxLength={20} aria-invalid={!!errors.name} {...form.register("name")} />
            {errors.name ? <FieldError>{errors.name.message}</FieldError> : null}
          </PanelRow>
          <PanelRow label="설명" htmlFor={`${id}-description`} top>
            <Textarea
              id={`${id}-description`}
              rows={3}
              maxLength={500}
              aria-invalid={!!errors.description}
              {...form.register("description")}
            />
            {errors.description ? <FieldError>{errors.description.message}</FieldError> : null}
          </PanelRow>
          {department ? <PanelRow label="직원">{department.employee_count}명</PanelRow> : null}
        </PanelSection>
        <PanelSection title="규칙">
          <Textarea
            aria-label="규칙"
            rows={5}
            placeholder="부서에서 지킬 규칙을 적어 주세요."
            {...form.register("rules")}
          />
        </PanelSection>
        {error ? <Alert variant="error" title={error} /> : null}
      </div>
      <div className="flex items-center gap-2 border-t border-border px-6 py-3">
        <div className="ml-auto flex gap-2">
          <Button type="button" variant="outline" onClick={onDone}>
            취소
          </Button>
          <Button type="submit" disabled={save.isPending}>
            저장
          </Button>
        </div>
      </div>
      <DiscardDialog blocker={blocker} />
    </form>
  );
}

function FieldError({ children }: { children: React.ReactNode }) {
  return <p className="mt-1 text-caption font-normal text-destructive-text">{children}</p>;
}

/** 부서 삭제: 남은 팀·직원·신청이 있으면 지울 수 없어 그 대상을 보여 준다 (A93·F69) */
function DeleteDepartmentDialog({
  department,
  onClose,
  onDeleted,
}: {
  department: Department;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const impact = useQuery(impactQuery("department", department.id));
  const remove = useDeleteDepartment();
  const [error, setError] = useState<string | null>(null);
  const blocked = impact.data ? hasImpact(impact.data) : false;
  const onDelete = async () => {
    setError(null);
    try {
      await remove.mutateAsync(department.id);
      toast.success(`${department.name} 부서를 삭제했어요`);
      onDeleted();
    } catch (e) {
      setError(errorText(e));
    }
  };
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-120 flex-col gap-4 p-6">
        <DialogTitle className="pr-8 text-h2 text-foreground">
          {blocked ? `${eul(department.name)} 지울 수 없어요` : `${eul(department.name)} 삭제할까요?`}
        </DialogTitle>
        <DialogDescription className="text-body text-muted-foreground">
          {blocked
            ? "아래 팀·직원·가입 신청을 먼저 다른 부서로 옮기거나 정리해야 지울 수 있어요."
            : "되돌릴 수 없어요."}
        </DialogDescription>
        {impact.isError ? <Alert variant="error" title="영향받는 대상을 불러오지 못했어요." /> : null}
        {blocked ? <ImpactList impact={impact.data} /> : null}
        {error ? <Alert variant="error" title={error} /> : null}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            {blocked ? "닫기" : "취소"}
          </Button>
          {blocked ? null : (
            <Button variant="destructive" disabled={!impact.data || remove.isPending} onClick={() => void onDelete()}>
              삭제
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
