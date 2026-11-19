import { TZDate } from "@date-fns/tz";
import { useQueries } from "@tanstack/react-query";
import { addDays } from "date-fns";
import { X } from "lucide-react";
import { useMemo, useState } from "react";

import { ErrorState } from "@/components/error-state";
import { Calendar } from "@/components/ui/calendar";
import { Spinner } from "@/components/ui/spinner";
import { formatKst, formatMinutes, TIME_ZONE } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { availableTimesQuery, type MentorCard } from "../api";
import { MAX_DESIRED } from "../draft";
import { slotLabel } from "@/features/requests/labels";
import { durationOptions, kstDateKey, MAX_DAYS_AHEAD, monthRanges, startTimes } from "../slots";
import { MentorAvatar } from "./mentor-step";

/**
 * ② 일정 선택 (Figma `Screen / 1:1 일정 선택`, A38·F30).
 * 진행 시간을 고르면 그 길이로 시작할 수 있는 30분 경계 시각만 칸으로 보인다. 희망 일시 1~3개.
 */
export function ScheduleStep({
  cohortId,
  mentor,
  unit,
  remaining,
  duration,
  desiredTimes,
  onChange,
}: {
  cohortId: string;
  mentor: MentorCard | undefined;
  unit: number;
  remaining: number;
  duration: number;
  desiredTimes: string[];
  onChange: (patch: { duration?: number; desiredTimes?: string[] }) => void;
}) {
  // 화면을 연 날 기준으로 조회 범위를 정한다 (오늘~60일)
  const [today] = useState(() => new Date());
  const [month, setMonth] = useState<Date>(() => {
    const t = new TZDate(today.getTime(), TIME_ZONE);
    return new TZDate(t.getFullYear(), t.getMonth(), 1, TIME_ZONE);
  });
  const ranges = monthRanges(month, today);
  const mentorId = mentor?.mentor_id ?? "";
  const results = useQueries({
    queries: ranges.map(([from, to]) => ({
      ...availableTimesQuery(mentorId, cohortId, from, to),
      enabled: !!mentorId,
    })),
  });
  const pending = results.some((r) => r.isPending);
  const failed = results.some((r) => r.isError);
  const intervals = results.flatMap((r) => r.data?.intervals ?? []);
  const leadHours = results.find((r) => r.data)?.data?.min_lead_hours;
  const byDay = useMemo(() => startTimes(intervals, duration), [intervals, duration]);
  const [day, setDay] = useState<string | null>(null);
  const shownDay = day && byDay.has(day) ? day : ([...byDay.keys()].sort()[0] ?? null);
  const options = durationOptions(unit, remaining);

  const toggle = (iso: string) => {
    if (desiredTimes.includes(iso)) onChange({ desiredTimes: desiredTimes.filter((t) => t !== iso) });
    else if (desiredTimes.length < MAX_DESIRED) onChange({ desiredTimes: [...desiredTimes, iso] });
  };
  const overlaps = (iso: string) => {
    const s = new Date(iso).getTime();
    return desiredTimes.some((t) => {
      if (t === iso) return false;
      const o = new Date(t).getTime();
      return s < o + duration * 60_000 && o < s + duration * 60_000;
    });
  };

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:gap-5">
      <section className="flex min-w-0 flex-1 flex-col gap-4 rounded-xl border border-border bg-card p-4 md:p-6">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-body-strong text-foreground">진행 시간</h2>
          <div role="radiogroup" aria-label="진행 시간" className="flex gap-1 rounded-md bg-muted p-0.5">
            {options.map((d) => (
              <button
                key={d}
                type="button"
                role="radio"
                aria-checked={d === duration}
                onClick={() => onChange({ duration: d, desiredTimes: [] })}
                className={cn(
                  "rounded-sm px-3 py-1 text-label outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  d === duration ? "bg-background text-foreground shadow-sm" : "text-muted-foreground",
                )}
              >
                {d}분
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-5 md:flex-row md:items-start">
          <Calendar
            mode="single"
            month={month}
            onMonthChange={setMonth}
            startMonth={today}
            endMonth={addDays(today, MAX_DAYS_AHEAD)}
            selected={shownDay ? new TZDate(`${shownDay}T12:00:00+09:00`, TIME_ZONE) : undefined}
            onSelect={(d) => d && setDay(kstDateKey(d))}
            disabled={(d) => !byDay.has(kstDateKey(d))}
            modifiers={{ available: (d) => byDay.has(kstDateKey(d)) }}
            className="w-full md:w-75 md:shrink-0"
          />
          <div className="flex min-w-0 flex-1 flex-col gap-3">
            {pending ? (
              <div className="flex justify-center py-6">
                <Spinner label="가능한 시간을 불러오는 중" />
              </div>
            ) : failed ? (
              <ErrorState
                title="가능한 시간을 불러오지 못했어요"
                onRetry={() => results.forEach((r) => void r.refetch())}
              />
            ) : shownDay ? (
              <>
                <h3 className="text-body-strong text-foreground">
                  {formatKst(`${shownDay}T12:00:00+09:00`, "M월 d일 (EEE)")}
                </h3>
                <ul
                  aria-label="시작 시각"
                  className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-3 xl:grid-cols-4"
                >
                  {(byDay.get(shownDay) ?? []).map((iso) => {
                    const chosen = desiredTimes.includes(iso);
                    const blocked = !chosen && (desiredTimes.length >= MAX_DESIRED || overlaps(iso));
                    return (
                      <li key={iso}>
                        <button
                          type="button"
                          aria-pressed={chosen}
                          disabled={blocked}
                          onClick={() => toggle(iso)}
                          className={cn(
                            "h-9 w-full rounded-md border text-body outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40",
                            chosen
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-input bg-background text-foreground hover:bg-accent",
                          )}
                        >
                          {formatKst(iso, "HH:mm")}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </>
            ) : (
              <p className="rounded-md bg-muted px-3 py-4 text-body-sm text-muted-foreground">
                이 달에는 {formatMinutes(duration)} 동안 신청할 수 있는 시간이 없어요. 다른 달이나 진행 시간을 골라
                보세요.
              </p>
            )}
            <p className="text-caption text-muted-foreground">
              고른 진행 시간으로 시작할 수 있는 시각만 보여요.
              {leadHours !== undefined ? ` 시작 ${leadHours}시간 전까지 신청할 수 있어요.` : ""}
            </p>
          </div>
        </div>
      </section>
      <aside className="flex flex-col gap-4 lg:w-85 lg:shrink-0">
        <section className="flex flex-col gap-2.5 rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-body-strong text-foreground">고른 희망 일시</h2>
            <span className="text-caption text-muted-foreground">
              {desiredTimes.length} / {MAX_DESIRED}
            </span>
          </div>
          {desiredTimes.length ? (
            <ol className="flex flex-col gap-2">
              {desiredTimes.map((t, i) => (
                <li key={t} className="flex items-center gap-2">
                  <span className="text-caption-strong text-primary-text">{i + 1}순위</span>
                  <span className="flex-1 text-body text-foreground">{slotLabel(t, duration)}</span>
                  <button
                    type="button"
                    aria-label={`${i + 1}순위 빼기`}
                    onClick={() => toggle(t)}
                    className="inline-flex size-6 items-center justify-center rounded-md text-muted-foreground hover:bg-accent"
                  >
                    <X aria-hidden className="size-3.5" />
                  </button>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-body-sm text-muted-foreground">달력에서 날짜를 고르고 시작 시각을 눌러 주세요.</p>
          )}
          <p className="text-caption text-muted-foreground">1순위부터 멘토가 확인해요. 한 개만 골라도 돼요.</p>
        </section>
        {mentor ? (
          <section className="flex items-center gap-3 rounded-xl border border-border bg-card p-5">
            <MentorAvatar mentor={mentor} size="md" />
            <div className="flex min-w-0 flex-col">
              <span className="text-body-strong text-foreground">{mentor.display_name}</span>
              {mentor.headline ? <span className="text-caption text-muted-foreground">{mentor.headline}</span> : null}
            </div>
          </section>
        ) : null}
      </aside>
    </div>
  );
}
