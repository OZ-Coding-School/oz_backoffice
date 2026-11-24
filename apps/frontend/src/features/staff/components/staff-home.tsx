import { useQuery } from "@tanstack/react-query";
import { LayoutGrid, ShieldQuestion } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { Spinner } from "@/components/ui/spinner";
import type { Me } from "@/features/auth/api";

import { staffAccessQuery } from "../api";

/** 운영진 홈 (임시, FE-14a). 처리할 일 요약은 FE-14b */
export function StaffHome({ me }: { me: Me }) {
  const access = useQuery(staffAccessQuery);
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-foreground">안녕하세요, {me.name}님</h1>
        <p className="text-body text-muted-foreground">오늘 처리할 일을 모아 볼 수 있어요.</p>
      </div>
      {access.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : access.data && access.data.permissions.length === 0 ? (
        <EmptyState
          icon={ShieldQuestion}
          title="아직 받은 권한이 없어요"
          description="담당 과정·기수가 정해지면 메뉴가 열려요. 운영 관리자에게 문의해 주세요."
        />
      ) : (
        <EmptyState
          icon={LayoutGrid}
          title="처리할 일 요약이 곧 여기에 모여요"
          description="가입 승인·운영진 승인·기록 미제출처럼 권한이 있는 일만 모아 보여 줄 거예요."
        />
      )}
    </div>
  );
}
