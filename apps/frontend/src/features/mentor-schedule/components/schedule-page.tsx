import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronLeft, ChevronRight, Pencil, Plus, Trash2 } from "lucide-react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { useState, type CSSProperties, type ReactNode } from "react";

import { ErrorState } from "@/components/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { kstDateKey } from "@/features/apply/slots";
import type { MentoringSession } from "@/features/sessions/api";
import { formatKst, formatKstDay } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { holidaysQuery, monthSessionsQueryOf, scheduleQueryOf } from "../api";
import { dayEvents, MAX_LANES, weekSegments, type CalendarEvent, type Segment } from "../calendar";
import { isLocked } from "../form";
import {
  addMonths,
  dayStartMs,
  isoWeekday,
  monthGridDays,
  monthOf,
  monthTitle,
  periodLabel,
  repeatLabel,
  type UnavailablePeriod,
} from "../schedule";
import { useScheduleScope } from "../scope";
import { AcceptingCard } from "./accepting-card";
import { DeleteUnavailableDialog, UnavailablePanel, type PanelState } from "./unavailable-dialogs";

const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];

/** 색 (F89): 개인 일정 파랑(info), 세션(멘토링) 보라(primary), 공휴일 빨강(참고용) */
const TONE = {
  personal: "border-info bg-info/15 text-info-text dark:bg-info/25",
  session: "border-primary bg-primary/12 text-sidebar-accent-foreground dark:bg-primary/25",
} as const;
const DOT = { personal: "bg-info", session: "bg-primary" } as const;

/** 막대 한 줄 높이·간격·첫 줄 위치(px, 위치 계산용) */
const LANE_PX = 18;
const LANE_GAP = 3;
const LANE_TOP = 30;

/** 개인 일정 상세·수정·삭제 열기 (F89) */
interface Editor {
  view: (period: UnavailablePeriod) => void;
  edit: (period: UnavailablePeriod) => void;
  remove: (period: UnavailablePeriod) => void;
  now: number;
}

type Holidays = Map<string, string>;

/** 멘토 일정 (Figma `일정 · 데스크톱 (월 달력)`, F87·F89·A37). 달력은 조회만, 추가는 오른쪽 [+] */
export function SchedulePage({ month, embedded = false }: { month: string; embedded?: boolean }) {
  const scope = useScheduleScope();
  const days = monthGridDays(month);
  const first = days[0] ?? `${month}-01`;
  const last = days.at(-1) ?? first;
  const schedule = useQuery(scheduleQueryOf(scope.mentorId));
  const sessions = useQuery(monthSessionsQueryOf(month, scope.mentorId));
  const holidays = useQuery(holidaysQuery(first, last));
  const [now] = useState(() => Date.now());
  const [panel, setPanel] = useState<PanelState | null>(null);
  const [deleting, setDeleting] = useState<UnavailablePeriod | null>(null);
  const today = kstDateKey(new Date(now));
  const editor: Editor = {
    view: (period) => setPanel({ mode: "view", period }),
    edit: (period) => setPanel({ mode: "edit", period, from: "list" }),
    remove: setDeleting,
    now,
  };
  const holidayMap: Holidays = new Map();
  for (const h of holidays.data?.items ?? []) {
    const prev = holidayMap.get(h.holiday_date);
    holidayMap.set(h.holiday_date, prev ? `${prev} · ${h.name}` : h.name);
  }

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div className="flex flex-col gap-1">
        {embedded ? null : <h1 className="text-h1 text-foreground">일정</h1>}
        <p className="text-body text-muted-foreground">
          {embedded
            ? "멘토 대신 개인 일정을 등록해요. 나머지 시간은 기수 운영시간 안에서 수강생이 신청할 수 있어요."
            : "개인 일정만 등록해요. 나머지 시간은 기수 운영시간 안에서 수강생이 신청할 수 있어요."}
        </p>
      </div>
      <UnavailablePanel state={panel} now={now} onChange={setPanel} onDelete={setDeleting} />
      <DeleteUnavailableDialog period={deleting} onClose={() => setDeleting(null)} onDeleted={() => setPanel(null)} />
      {schedule.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : schedule.isError ? (
        <ErrorState onRetry={() => void schedule.refetch()} />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_22.5rem] lg:items-start lg:gap-6">
          {/* 휴대폰·태블릿은 신청 받기 → 달력 → 개인 일정, 넓은 화면은 오른쪽 열에 신청 받기·개인 일정 (F87) */}
          <div className="flex flex-col gap-4 max-lg:contents lg:order-2">
            <div className="max-lg:order-1">
              <AcceptingCard accepting={schedule.data.accepting_requests} readOnly={scope.readOnly} />
            </div>
            <div className="max-lg:order-3">
              <PeriodList
                periods={schedule.data.unavailable_periods}
                editor={editor}
                onAdd={() => setPanel({ mode: "add", day: monthOf(today) === month ? today : `${month}-01` })}
              />
            </div>
          </div>
          <div className="max-lg:order-2 lg:order-1">
            <MonthCard
              key={month}
              month={month}
              days={days}
              today={today}
              periods={schedule.data.unavailable_periods}
              sessions={sessions.data?.items ?? []}
              holidays={holidayMap}
              editor={editor}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function MonthCard({
  month,
  days,
  today,
  periods,
  sessions,
  holidays,
  editor,
}: {
  month: string;
  days: string[];
  today: string;
  periods: UnavailablePeriod[];
  sessions: MentoringSession[];
  holidays: Holidays;
  editor: Editor;
}) {
  const navigate = useNavigate();
  const scope = useScheduleScope();
  const thisMonth = monthOf(today);
  const [picked, setPicked] = useState(thisMonth === month ? today : `${month}-01`);
  const goTo = (target: string) =>
    scope.onMonth ? scope.onMonth(target) : void navigate({ to: "/mentor/schedule", search: { month: target } });
  const events = days.map((day) => dayEvents(day, periods, sessions));
  const weeks = Array.from({ length: days.length / 7 }, (_, w) => w * 7);
  const pickedEvents = events[days.indexOf(picked)] ?? [];

  return (
    <section
      aria-label="월간 일정"
      className="flex min-w-0 flex-col gap-3 rounded-2xl border border-border bg-card shadow-sm p-4 md:p-5"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-h3 text-foreground">{monthTitle(month)}</h2>
        <div className="flex items-center gap-3 text-caption text-muted-foreground max-md:order-last max-md:w-full md:ml-3">
          <Legend className="bg-destructive">공휴일</Legend>
          <Legend className={DOT.personal}>개인 일정</Legend>
          <Legend className={DOT.session}>멘토링</Legend>
        </div>
        <div className="ml-auto flex items-center gap-1">
          <Button variant="outline" size="sm" disabled={month === thisMonth} onClick={() => goTo(thisMonth)}>
            오늘
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="size-8 px-0"
            aria-label="이전 달"
            onClick={() => goTo(addMonths(month, -1))}
          >
            <ChevronLeft aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="size-8 px-0"
            aria-label="다음 달"
            onClick={() => goTo(addMonths(month, 1))}
          >
            <ChevronRight aria-hidden />
          </Button>
        </div>
      </div>

      {/* 태블릿 이상: 날짜 칸에 일정 막대, 이어지는 개인 일정은 한 막대 (F89) */}
      <div role="region" aria-label="월 달력" className="hidden md:block">
        <div className="grid grid-cols-7 pb-2">
          {WEEKDAYS.map((d, i) => (
            <span
              key={d}
              className={cn("text-center text-caption", i > 4 ? "text-muted-foreground" : "text-foreground")}
            >
              {d}
            </span>
          ))}
        </div>
        <div className="overflow-hidden rounded-lg border-t border-l border-border">
          {weeks.map((start) => (
            <WeekRow
              key={days[start]}
              days={days.slice(start, start + 7)}
              events={events.slice(start, start + 7)}
              month={month}
              today={today}
              holidays={holidays}
              editor={editor}
            />
          ))}
        </div>
      </div>

      {/* 휴대폰: 작은 달력(색 점) + 고른 날 목록 (F89) */}
      <div className="flex flex-col gap-3 md:hidden">
        <div className="grid grid-cols-7">
          {WEEKDAYS.map((d, i) => (
            <span
              key={d}
              className={cn("pb-1 text-center text-caption", i > 4 ? "text-muted-foreground" : "text-foreground")}
            >
              {d}
            </span>
          ))}
          {days.map((day, i) => {
            const kinds = new Set((events[i] ?? []).map((e) => e.kind));
            return (
              <button
                key={day}
                type="button"
                aria-pressed={day === picked}
                aria-label={dayName(day)}
                onClick={() => setPicked(day)}
                className={cn(
                  "flex flex-col items-center gap-1 rounded-lg py-1 outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  day === picked && "bg-sidebar-accent",
                  monthOf(day) !== month && "opacity-50",
                )}
              >
                <DayNumber day={day} today={today} holiday={holidays.has(day)} short />
                <span aria-hidden className="flex h-1.5 gap-0.5">
                  {(["personal", "session"] as const)
                    .filter((k) => kinds.has(k))
                    .map((k) => (
                      <span key={k} className={cn("size-1.5 rounded-full", DOT[k])} />
                    ))}
                </span>
              </button>
            );
          })}
        </div>
        <div role="region" aria-label="고른 날 일정" className="flex flex-col gap-2 border-t border-border pt-3">
          <h3 className="flex flex-wrap items-center gap-2 text-body-strong text-foreground">
            {formatKstDay(dayStartMs(picked))} · {pickedEvents.length}건
            {holidays.has(picked) ? (
              <span className="text-caption text-destructive-text">{holidays.get(picked)}</span>
            ) : null}
          </h3>
          {pickedEvents.length === 0 ? (
            <p className="text-body-sm text-muted-foreground">일정이 없어요.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {pickedEvents.map((e) => (
                <li key={e.id}>
                  <EventItem event={e} editor={editor} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}

function Legend({ className, children }: { className: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden className={cn("h-3 w-1 rounded-full", className)} />
      {children}
    </span>
  );
}

function dayName(day: string): string {
  return formatKst(dayStartMs(day), "M월 d일 (EEE)");
}

/** 날짜 숫자. 오늘은 primary 원, 공휴일은 빨강, 주말은 흐리게. 큰 달력의 1일은 "11월 1일" */
function DayNumber({
  day,
  today,
  holiday,
  short = false,
}: {
  day: string;
  today: string;
  holiday: boolean;
  short?: boolean;
}) {
  const first = !short && day.endsWith("-01");
  return (
    <span
      className={cn(
        "inline-flex h-6 min-w-6 shrink-0 items-center justify-center rounded-full text-label",
        first && "px-1.5",
        day === today
          ? "bg-primary text-body-strong text-primary-foreground"
          : holiday
            ? "text-body-strong text-destructive-text"
            : isoWeekday(day) > 5
              ? "text-muted-foreground"
              : "text-foreground",
      )}
    >
      {first ? `${Number(day.slice(5, 7))}월 1일` : Number(day.slice(8))}
    </span>
  );
}

function WeekRow({
  days,
  events,
  month,
  today,
  holidays,
  editor,
}: {
  days: string[];
  events: CalendarEvent[][];
  month: string;
  today: string;
  holidays: Holidays;
  editor: Editor;
}) {
  const { segments, hidden } = weekSegments(events);
  return (
    <div className="relative h-28">
      <div className="grid h-full grid-cols-7">
        {days.map((day, col) => {
          const holiday = holidays.get(day);
          const more = hidden[col] ?? 0;
          return (
            <div
              key={day}
              role="group"
              aria-label={dayName(day)}
              className={cn(
                "relative flex flex-col border-r border-b border-border px-1 pt-1",
                day === today ? "bg-sidebar-accent/40" : holiday ? "bg-destructive/8" : null,
              )}
            >
              <div className={cn("flex min-w-0 items-center gap-1", monthOf(day) !== month && "opacity-50")}>
                <DayNumber day={day} today={today} holiday={!!holiday} />
                {holiday ? <span className="truncate text-caption text-destructive-text">{holiday}</span> : null}
              </div>
              {more > 0 ? <MoreButton day={day} count={more} events={events[col] ?? []} editor={editor} /> : null}
            </div>
          );
        })}
      </div>
      {segments
        .filter((s) => s.lane < MAX_LANES)
        .map((s) => (
          <Bar
            key={`${s.event.id}-${s.from}`}
            segment={s}
            dim={monthOf(days[s.from] ?? "") !== month}
            editor={editor}
          />
        ))}
    </div>
  );
}

/** 일정 막대: 이어지는 개인 일정은 여러 칸에 걸친다 */
function Bar({ segment: s, dim, editor }: { segment: Segment; dim: boolean; editor: Editor }) {
  const span = s.to - s.from + 1;
  // 칸 위치에서 계산하는 값이라 인라인 스타일
  const style: CSSProperties = {
    left: `calc(${(s.from / 7) * 100}% + 3px)`,
    width: `calc(${(span / 7) * 100}% - 6px)`,
    top: `${LANE_TOP + s.lane * (LANE_PX + LANE_GAP)}px`,
    height: `${LANE_PX}px`,
  };
  return (
    <EventTrigger
      event={s.event}
      editor={editor}
      style={style}
      className={cn(
        "absolute z-10 flex items-center gap-1 overflow-hidden rounded-sm border-l-3 pr-1 pl-1.5 text-left text-caption leading-none",
        TONE[s.event.kind],
        dim && "opacity-50",
      )}
    >
      <span className="shrink-0 font-semibold">{s.event.time}</span>
      <span className="truncate">{s.event.label}</span>
    </EventTrigger>
  );
}

/** 누르면 개인 일정은 상세 패널, 세션은 세션 상세(멘토 본인만) */
function EventTrigger({
  event,
  editor,
  className,
  style,
  children,
}: {
  event: CalendarEvent;
  editor: Editor;
  className: string;
  style?: CSSProperties;
  children: ReactNode;
}) {
  const scope = useScheduleScope();
  const name = `${event.label} ${event.time}`;
  const interactive = "outline-none hover:brightness-95 focus-visible:ring-2 focus-visible:ring-ring";
  const period = event.period;
  if (period)
    return (
      <button
        type="button"
        aria-label={name}
        style={style}
        onClick={() => editor.view(period)}
        className={cn(className, interactive)}
      >
        {children}
      </button>
    );
  // 운영진 일정 대리(F85)에는 세션 상세 화면이 아직 없어 보여 주기만 한다
  if (event.session && !scope.mentorId)
    return (
      <Link
        to="/mentor/sessions/$sessionId"
        params={{ sessionId: event.session.id }}
        aria-label={name}
        style={style}
        className={cn(className, interactive)}
      >
        {children}
      </Link>
    );
  return (
    <span role="img" aria-label={name} style={style} className={className}>
      {children}
    </span>
  );
}

/** 휴대폰 고른 날 목록 한 줄 */
function EventItem({ event, editor }: { event: CalendarEvent; editor: Editor }) {
  return (
    <EventTrigger
      event={event}
      editor={editor}
      className={cn("flex w-full items-center gap-3 rounded-lg border-l-3 px-3 py-2.5 text-left", TONE[event.kind])}
    >
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-body-strong">{event.time}</span>
        <span className="truncate text-body">{event.label}</span>
      </span>
    </EventTrigger>
  );
}

/** 칸에 다 못 보인 일정: '+N개'를 누르면 그날 전체 목록 */
function MoreButton({
  day,
  count,
  events,
  editor,
}: {
  day: string;
  count: number;
  events: CalendarEvent[];
  editor: Editor;
}) {
  return (
    <PopoverPrimitive.Root>
      <PopoverPrimitive.Trigger
        aria-label={`${dayName(day)} 일정 ${count}개 더 보기`}
        className="absolute bottom-1 left-1.5 z-10 rounded px-1 text-caption text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        +{count}개
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          side="bottom"
          align="start"
          sideOffset={4}
          aria-label={`${dayName(day)} 일정`}
          className="z-50 flex w-64 flex-col gap-1.5 rounded-lg border border-border bg-popover p-3 shadow-md"
        >
          <p className="pb-1 text-body-strong text-foreground">{formatKstDay(dayStartMs(day))}</p>
          {events.map((e) => (
            <EventTrigger
              key={e.id}
              event={e}
              editor={editor}
              className={cn(
                "flex items-center gap-1.5 rounded-sm border-l-3 px-2 py-1 text-left text-caption",
                TONE[e.kind],
              )}
            >
              <span className="shrink-0 font-semibold">{e.time}</span>
              <span className="truncate">{e.label}</span>
            </EventTrigger>
          ))}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}

function PeriodList({ periods, editor, onAdd }: { periods: UnavailablePeriod[]; editor: Editor; onAdd: () => void }) {
  const scope = useScheduleScope();
  return (
    <section
      aria-labelledby="periods-title"
      className="flex flex-col gap-3 rounded-2xl border border-border bg-card shadow-sm p-4 md:p-5"
    >
      <div className="flex items-center gap-2">
        <h2 id="periods-title" className="flex-1 text-h3 text-foreground">
          개인 일정
        </h2>
        <Button
          variant="outline"
          size="sm"
          className="size-8 px-0"
          aria-label="개인 일정 추가"
          disabled={scope.readOnly}
          onClick={onAdd}
        >
          <Plus aria-hidden />
        </Button>
      </div>
      {periods.length === 0 ? (
        <p className="text-body-sm text-muted-foreground">
          등록한 개인 일정이 없어요. 나머지 시간은 모두 신청을 받아요.
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-border border-t border-border">
          {periods.map((p) => (
            <li key={p.id} className="flex items-start gap-2 py-3">
              <button
                type="button"
                aria-label={`${p.category ?? "개인 일정"} 보기`}
                onClick={() => editor.view(p)}
                className="flex min-w-0 flex-1 flex-col gap-0.5 rounded-md text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="flex items-center gap-2">
                  <span className="text-body-strong text-foreground">{p.category ?? "개인 일정"}</span>
                  <Badge variant="outline">{repeatLabel(p)}</Badge>
                </span>
                <span className="text-caption text-muted-foreground">{periodLabel(p)}</span>
                {p.reason ? <span className="text-caption text-muted-foreground">{p.reason}</span> : null}
              </button>
              {isLocked(p, editor.now) || scope.readOnly ? null : (
                <span className="flex shrink-0 gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="size-8 px-0 text-muted-foreground hover:text-foreground"
                    aria-label={`${p.category ?? "개인 일정"} 수정`}
                    onClick={() => editor.edit(p)}
                  >
                    <Pencil aria-hidden />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="size-8 px-0 text-muted-foreground hover:bg-destructive-subtle hover:text-destructive-text"
                    aria-label={`${p.category ?? "개인 일정"} 삭제`}
                    onClick={() => editor.remove(p)}
                  >
                    <Trash2 aria-hidden />
                  </Button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="text-caption text-muted-foreground">
        수강생은 기수 운영시간 안에서만 신청해요. 기수마다 운영시간이 달라요. 공휴일은 참고로만 보여요.
      </p>
    </section>
  );
}
