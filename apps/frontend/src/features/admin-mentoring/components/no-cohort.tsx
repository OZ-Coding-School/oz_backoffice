/** 고를 기수가 없을 때 (담당 기수 없음, F90) */
export function NoCohort() {
  return (
    <div className="flex flex-col items-center gap-2 py-20 text-center">
      <p className="text-h3 text-foreground">볼 수 있는 기수가 없어요</p>
      <p className="text-body text-muted-foreground">담당 기수가 정해지면 여기서 기수별 멘토링을 관리할 수 있어요.</p>
    </div>
  );
}
