import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { CalendarDays, ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { useMemo } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { errorText } from "@/features/admin-org/text";
import { hasPermission, staffAccessQuery } from "@/features/staff/api";
import { formatKst } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { holidaysQuery, useSyncHolidays, type Holiday } from "../api";
import { kstYear, monthCells, weekday, WEEKDAY_LABELS } from "../calendar";
import { DayPanel, HolidayList } from "./day-panel";

export interface HolidaysSearch {
  year?: number;
  date?: string;
}

/** 설정 > 공휴일 (F72): 1~12월 달력 + 오른쪽 선택한 날 칸 */
export function HolidaysPage({ search }: { search: HolidaysSearch }) {
  const year = search.year ?? kstYear();
  const selected = search.date?.startsWith(`${year}-`) ? search.date : undefined;
  const list = useQuery(holidaysQuery(year));
  const access = useQuery(staffAccessQuery);
  const canManage = !!access.data && hasPermission(access.data, "mentoring.settings.manage");
  const holidays = useMemo(() => list.data?.items ?? [], [list.data]);
  const byDate = useMemo(() => {
    const map = new Map<string, Holiday[]>();
    for (const h of holidays) map.set(h.holiday_date, [...(map.get(h.holiday_date) ?? []), h]);
    return map;
  }, [holidays]);
  const publicDays = new Set(holidays.filter((h) => h.source === "PUBLIC").map((h) => h.holiday_date)).size;
  const customDays = holidays.filter((h) => h.source === "CUSTOM").length;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        icon={CalendarDays}
        title="공휴일"
        description="법정공휴일은 자동으로 정해지고, 추가 휴일은 직접 등록해요."
      />
      <div className="flex items-center gap-3">
        <YearLink year={year - 1} label="이전 해" icon={ChevronLeft} />
        <h2 className="text-h2 text-foreground">{year}년</h2>
        <YearLink year={year + 1} label="다음 해" icon={ChevronRight} />
        {list.data ? (
          <ul aria-label="범례" className="ml-2 flex items-center gap-4 text-caption text-muted-foreground">
            <li className="flex items-center gap-1.5">
              <span aria-hidden className="size-2 rounded-full bg-destructive" />
              법정공휴일 {publicDays}일
            </li>
            <li className="flex items-center gap-1.5">
              <span aria-hidden className="size-2 rounded-full bg-primary" />
              추가 휴일 {customDays}일
            </li>
          </ul>
        ) : null}
        <div className="flex-1" />
        {list.data ? (
          <span className="text-caption text-muted-foreground">
            {list.data.synced_at
              ? `법정공휴일 마지막 동기화 ${formatKst(list.data.synced_at, "M/d HH:mm")}`
              : "법정공휴일을 아직 가져오지 않았어요"}
          </span>
        ) : null}
        {canManage ? <SyncButton /> : null}
      </div>
      {list.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : list.isError ? (
        <ErrorState onRetry={() => void list.refetch()} />
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)_280px] items-start gap-6">
          <div className="grid grid-cols-4 gap-2.5">
            {Array.from({ length: 12 }, (_, i) => (
              <MonthCard key={i} year={year} month={i + 1} byDate={byDate} selected={selected} />
            ))}
          </div>
          {selected ? (
            <DayPanel
              key={selected}
              date={selected}
              holidays={byDate.get(selected) ?? []}
              custom={holidays.filter((h) => h.source === "CUSTOM")}
              year={year}
              canManage={canManage}
            />
          ) : (
            <section
              aria-label={`${year}년 공휴일`}
              className="sticky top-6 flex max-h-[calc(100vh-3rem)] flex-col gap-3 overflow-y-auto rounded-2xl border border-border bg-card shadow-sm p-4"
            >
              <h3 className="text-body-strong text-foreground">{year}년 공휴일</h3>
              <HolidayList label={`${year}년 공휴일`} year={year} items={holidays} empty="공휴일이 없어요." />
            </section>
          )}
        </div>
      )}
    </div>
  );
}

function YearLink({ year, label, icon: Icon }: { year: number; label: string; icon: typeof ChevronLeft }) {
  return (
    <Link
      to="/admin/settings/holidays"
      search={{ year }}
      aria-label={label}
      className="inline-flex size-8 items-center justify-center rounded-md border border-input bg-background text-foreground outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Icon className="size-4" aria-hidden />
    </Link>
  );
}

function SyncButton() {
  const sync = useSyncHolidays();
  const onClick = async () => {
    try {
      const result = await sync.mutateAsync();
      const counts = result.years.map((y) => `${y.year}년 ${y.holiday_count}일`).join(" · ");
      toast.success(`법정공휴일을 가져왔어요 (${counts})`);
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  return (
    <Button variant="outline" size="sm" disabled={sync.isPending} onClick={() => void onClick()}>
      <RefreshCw aria-hidden className={cn(sync.isPending && "animate-spin")} />
      지금 가져오기
    </Button>
  );
}

function MonthCard({
  year,
  month,
  byDate,
  selected,
}: {
  year: number;
  month: number;
  byDate: Map<string, Holiday[]>;
  selected: string | undefined;
}) {
  return (
    <section aria-label={`${month}월`} className="flex flex-col gap-1 rounded-lg border border-border bg-card p-2.5">
      <h3 className="px-1 text-body-strong text-foreground">{month}월</h3>
      <div className="grid grid-cols-7 gap-y-0.5 text-center">
        {WEEKDAY_LABELS.map((w, i) => (
          <span key={w} className={cn("text-caption", i === 0 ? "text-destructive-text" : "text-muted-foreground")}>
            {w}
          </span>
        ))}
        {monthCells(year, month).map((key, i) =>
          key ? (
            <DayCell key={key} day={key} holidays={byDate.get(key) ?? []} selected={key === selected} />
          ) : (
            <span key={`empty-${i}`} />
          ),
        )}
      </div>
    </section>
  );
}

function DayCell({ day, holidays, selected }: { day: string; holidays: Holiday[]; selected: boolean }) {
  const isPublic = holidays.some((h) => h.source === "PUBLIC");
  const isCustom = holidays.some((h) => h.source === "CUSTOM");
  const number = Number(day.slice(8));
  const names = holidays.map((h) => h.name).join(", ");
  return (
    <Link
      to="/admin/settings/holidays"
      search={{ year: Number(day.slice(0, 4)), date: day }}
      aria-label={`${Number(day.slice(5, 7))}월 ${number}일${names ? ` ${names}` : ""}`}
      aria-current={selected ? "date" : undefined}
      title={names || undefined}
      className={cn(
        "mx-auto flex size-6 items-center justify-center rounded-full text-caption outline-none hover:ring-1 hover:ring-primary focus-visible:ring-2 focus-visible:ring-ring",
        selected
          ? "bg-primary text-primary-foreground"
          : isPublic
            ? "bg-destructive-subtle text-destructive-text"
            : isCustom
              ? "bg-accent text-primary-text"
              : weekday(day) === 0
                ? "text-destructive-text"
                : "text-foreground",
      )}
    >
      {number}
    </Link>
  );
}
