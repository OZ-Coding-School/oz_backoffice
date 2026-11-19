import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";

import { expertiseChips, mentorQuery } from "../api";
import { Chips, MentorAvatar } from "./mentor-step";

/** 멘토 상세 소개 모달 (Figma `Screen / 1:1 멘토 소개 (모달)`, A64). 실명·연락처는 없다 */
export function MentorDialog({
  cohortId,
  mentorId,
  onClose,
  onSelect,
}: {
  cohortId: string;
  mentorId: string | null;
  onClose: () => void;
  /** 없으면 닫기만 있다 (팀 담당 멘토 확인, F31) */
  onSelect?: (mentorId: string) => void;
}) {
  const mentor = useQuery({ ...mentorQuery(cohortId, mentorId ?? ""), enabled: !!mentorId });
  return (
    <Dialog open={!!mentorId} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-w-140 flex-col gap-4 p-6">
        {mentor.data ? (
          <>
            <div className="flex items-start gap-3 pr-8">
              <MentorAvatar mentor={mentor.data} />
              <div className="flex min-w-0 flex-col">
                <DialogTitle className="text-h2 text-foreground">{mentor.data.display_name}</DialogTitle>
                <DialogDescription className="text-caption text-muted-foreground">
                  {mentor.data.headline ?? "멘토 소개"}
                </DialogDescription>
              </div>
            </div>
            {mentor.data.accepting_requests ? (
              <Badge variant="success" className="w-fit">
                신청 받는 중
              </Badge>
            ) : (
              <Badge variant="secondary" className="w-fit">
                지금은 신청을 받지 않아요
              </Badge>
            )}
            {expertiseChips(mentor.data.expertise).length ? (
              <section className="flex flex-col gap-2">
                <h3 className="text-caption text-muted-foreground">전문 분야</h3>
                <Chips items={expertiseChips(mentor.data.expertise)} />
              </section>
            ) : null}
            {mentor.data.introduction ? (
              <section className="flex flex-col gap-2">
                <h3 className="text-caption text-muted-foreground">소개</h3>
                <p className="whitespace-pre-line text-body text-foreground">{mentor.data.introduction}</p>
              </section>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={onClose}>
                닫기
              </Button>
              {onSelect && mentor.data.accepting_requests ? (
                <Button onClick={() => onSelect(mentor.data.mentor_id)}>이 멘토 선택</Button>
              ) : null}
            </div>
          </>
        ) : (
          <div className="flex justify-center py-10">
            <DialogTitle className="sr-only">멘토 소개</DialogTitle>
            <Spinner />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
