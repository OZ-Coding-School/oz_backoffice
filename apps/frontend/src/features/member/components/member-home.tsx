import { LayoutGrid } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import type { Me } from "@/features/auth/api";
import { StudentHome } from "@/features/home/components/student-home";

/** 회원 홈 (F27). 수강생은 할 일 요약(FE-8, F42), 멘토는 FE-13까지 인사말 + 빈 상태 */
export function MemberHome({ me }: { me: Me }) {
  if (me.account_type === "STUDENT") return <StudentHome me={me} />;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">안녕하세요, {me.name}님</h1>
        <p className="text-body text-muted-foreground">오늘 확인할 일을 모아 봤어요.</p>
      </div>
      <EmptyState
        icon={LayoutGrid}
        title="처리할 신청·오늘 세션이 곧 여기에 모여요"
        description="받은 신청·세션 화면이 열리면 오늘 확인할 일을 여기에서 바로 볼 수 있어요."
      />
    </div>
  );
}
