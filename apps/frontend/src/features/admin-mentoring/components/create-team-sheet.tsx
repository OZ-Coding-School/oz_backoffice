import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { PanelHead, PanelRow, PanelSection } from "@/components/panel";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";

import { cohortMentorsQuery, unassignedQuery, useCreateTeam } from "../teams-api";

const NAME_MAX = 30;

const ERROR_MESSAGES: Record<string, string> = {
  team_mentoring_not_allowed: "이 기수는 팀 멘토링을 받지 않아요. 멘토링 설정에서 켜 주세요.",
  mentoring_settings_not_configured: "이 기수의 멘토링 설정을 먼저 저장해 주세요.",
  mentor_not_assigned: "이 기수에 활성 배정된 멘토만 팀을 맡을 수 있어요.",
  student_not_enrolled: "수강 중인 수강생만 팀에 넣을 수 있어요.",
  student_in_other_team: "이미 다른 팀에 속한 수강생이 있어요. 목록을 새로 불러와 주세요.",
};

/** 팀 만들기 패널 (F68·F93·A39): 이름(선택) · 담당 멘토(활성 배정) · 팀원(팀 없는 수강 중 수강생) */
export function CreateTeamSheet({
  cohortId,
  cohortTitle,
  onClose,
}: {
  cohortId: string;
  cohortTitle: string;
  onClose: () => void;
}) {
  const id = useId();
  const mentors = useQuery(cohortMentorsQuery(cohortId));
  const students = useQuery(unassignedQuery(cohortId));
  const create = useCreateTeam(cohortId);
  const [name, setName] = useState("");
  const [mentorId, setMentorId] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const active = (mentors.data ?? []).filter((a) => a.is_active);

  const submit = async () => {
    setError(null);
    if (!mentorId) {
      setError("담당 멘토를 골라 주세요.");
      return;
    }
    try {
      const team = await create.mutateAsync({ name: name.trim() || null, mentor_id: mentorId, student_ids: picked });
      toast.success(`${team.label}을 만들었어요`);
      onClose();
    } catch (e) {
      const code = e instanceof ApiError ? e.code : undefined;
      setError((code && ERROR_MESSAGES[code]) ?? "팀을 만들지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  };

  return (
    <Sheet open onOpenChange={(open) => (open ? undefined : onClose())}>
      <SheetContent aria-describedby={undefined} className="w-120">
        <PanelHead title="팀 만들기" description={cohortTitle} onClose={onClose} />
        <form
          aria-label="팀 만들기"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
          className="flex min-h-0 flex-1 flex-col"
        >
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-6">
            <PanelSection title="팀">
              <PanelRow
                label="이름"
                htmlFor={`${id}-name`}
                help="비우면 'N팀'으로 불러요. 번호는 기수 안에서 자동으로 붙어요."
              >
                <Input
                  id={`${id}-name`}
                  maxLength={NAME_MAX}
                  placeholder="예: 알파"
                  className="font-normal"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </PanelRow>
              <PanelRow label="담당 멘토" help="이 기수에 활성 배정된 멘토만 고를 수 있어요. 나중에 바꿀 수 있어요.">
                {mentors.isPending ? (
                  <Spinner />
                ) : active.length === 0 ? (
                  <span className="text-body font-normal text-muted-foreground">활성 배정된 멘토가 없어요</span>
                ) : (
                  <Select value={mentorId} onValueChange={setMentorId}>
                    <SelectTrigger aria-label="담당 멘토" className="font-normal">
                      <SelectValue placeholder="멘토 고르기" />
                    </SelectTrigger>
                    <SelectContent>
                      {active.map((a) => (
                        <SelectItem key={a.mentor_id} value={a.mentor_id}>
                          {a.mentor_display_name !== a.mentor_name
                            ? `${a.mentor_display_name} (${a.mentor_name})`
                            : a.mentor_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </PanelRow>
            </PanelSection>
            <PanelSection title={`팀원 · ${picked.length}명 선택`}>
              {students.isPending ? (
                <Spinner />
              ) : (students.data ?? []).length === 0 ? (
                <p className="text-body text-muted-foreground">팀이 없는 수강 중 수강생이 없어요.</p>
              ) : (
                <ul aria-label="팀 없는 수강생" className="flex max-h-80 flex-col overflow-y-auto">
                  {(students.data ?? []).map((s) => (
                    <li key={s.student_id}>
                      <label className="flex items-center gap-3 rounded-md px-1 py-2 hover:bg-muted/60">
                        <Checkbox
                          checked={picked.includes(s.student_id)}
                          onCheckedChange={() =>
                            setPicked((p) =>
                              p.includes(s.student_id) ? p.filter((x) => x !== s.student_id) : [...p, s.student_id],
                            )
                          }
                          aria-label={s.name}
                        />
                        <span className="flex-1 text-body text-foreground">{s.name}</span>
                        {s.is_signed_up ? null : <Badge variant="outline">미가입</Badge>}
                      </label>
                    </li>
                  ))}
                </ul>
              )}
            </PanelSection>
            {error ? <Alert variant="error" title={error} /> : null}
          </div>
          <div className="flex justify-end gap-2 border-t border-border px-6 py-3">
            <Button type="button" variant="outline" onClick={onClose}>
              취소
            </Button>
            <Button type="submit" disabled={create.isPending}>
              만들기
            </Button>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  );
}
