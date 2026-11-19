import { LayoutGrid } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import type { Me } from "@/features/auth/api";

/** 회원 홈 (FE-2: 인사말 + 빈 상태, F27). 할 일 요약은 FE-8(수강생)·FE-13(멘토)에서 채운다. */
export function MemberHome({ me }: { me: Me }) {
  const mentor = me.account_type === "MENTOR";
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">안녕하세요, {me.name}님</h1>
        <p className="text-body text-muted-foreground">오늘 확인할 일을 모아 봤어요.</p>
      </div>
      <EmptyState
        icon={LayoutGrid}
        title={mentor ? "처리할 신청·오늘 세션이 곧 여기에 모여요" : "할 일 요약이 곧 여기에 모여요"}
        description={
          mentor
            ? "받은 신청·세션 화면이 열리면 오늘 확인할 일을 여기에서 바로 볼 수 있어요."
            : "멘토링 신청·진행 기록 같은 화면이 열리면 오늘 확인할 일을 여기에서 바로 볼 수 있어요."
        }
      />
    </div>
  );
}
