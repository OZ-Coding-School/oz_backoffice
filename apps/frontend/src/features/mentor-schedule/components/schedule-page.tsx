import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronLeft, ChevronRight, Pencil, Plus, Trash2 } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type MouseEvent } from "react";

import { ErrorState } from "@/components/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { kstDateKey } from "@/features/apply/slots";
import { targetLabel } from "@/features/mentor-sessions/labels";
import type { MentoringSession } from "@/features/sessions/api";
import { formatKst } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { scheduleQueryOf, weekSessionsQueryOf } from "../api";
import { isLocked } from "../form";
import {
  addDays,
  dayStartMs,
  isoWeekday,
  daySegment,
  occurrences,
  periodLabel,
  repeatLabel,
  weekDays,
  weekdayLabel,
  weekStart,
  weekTitle,
  type UnavailablePeriod,
} from "../schedule";
import { useScheduleScope } from "../scope";
import { AcceptingCard } from "./accepting-card";
import { DeleteUnavailableDialog, UnavailableDialog } from "./unavailable-dialogs";

const DAY_MINUTES = 24 * 60;
/** 처음 보이는 시각 (F52) */
const FIRST_VISIBLE_HOUR = 8;
const HOURS = Array.from({ length: 24 }, (_, h) => h);
/** 한 시간 칸 높이(px). `h-12`와 같아야 한다 */
const HOUR_PX = 48;
const SLOT_MINUTES = 30;

interface Block {
  id: string;
  kind: "unavailable" | "session";
  label: string;
  start: number; // 그날 00:00 기준 분
  end: number;
  sessionId?: string;
  period?: UnavailablePeriod;
}

/** 추가·수정·삭제 창 열기 (F53·F88) */
interface Editor {
  add: (day: string, time: string) => void;
  edit: (period: UnavailablePeriod) => void;
  remove: (period: UnavailablePeriod) => void;
  now: number;
}

/** 멘토 일정 (Figma `일정 · 보기 (FE-11a)`, F51·F52·A37) */
export function SchedulePage({ monday, embedded = false }: { monday: string; embedded?: boolean }) {
  const scope = useScheduleScope();
  const schedule = useQuery(scheduleQueryOf(scope.mentorId));
  const sessions = useQuery(weekSessionsQueryOf(monday, scope.mentorId));
  const [now] = useState(() => Date.now());
  const [dialog, setDialog] = useState<{
    open: boolean;
    period: UnavailablePeriod | null;
    day?: string;
    time?: string;
  }>({ open: false, period: null });
  const [deleting, setDeleting] = useState<UnavailablePeriod | null>(null);
  const editor: Editor = {
    add: (day, time) => setDialog({ open: true, period: null, day, time }),
    edit: (period) => setDialog({ open: true, period }),
    remove: setDeleting,
    now,
  };
  const today = kstDateKey(new Date(now));

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start">
        <div className="flex flex-1 flex-col gap-1">
          {embedded ? null : <h1 className="text-h1 text-foreground">일정</h1>}
          <p className="text-body text-muted-foreground">
            {embedded
              ? "멘토 대신 안 되는 시간을 등록해요. 나머지 시간은 기수 운영시간 안에서 수강생이 신청할 수 있어요."
              : "안 되는 시간만 등록해요. 나머지 시간은 기수 운영시간 안에서 수강생이 신청할 수 있어요."}
          </p>
        </div>
      </div>
      <UnavailableDialog
        open={dialog.open}
        period={dialog.period}
        defaultDay={dialog.day ?? (weekDays(monday).includes(today) ? today : monday)}
        defaultTime={dialog.time}
        onOpenChange={(open) => setDialog((d) => ({ ...d, open }))}
      />
      <DeleteUnavailableDialog period={deleting} onClose={() => setDeleting(null)} />
      {schedule.isPending ? (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      ) : schedule.isError ? (
        <ErrorState onRetry={() => void schedule.refetch()} />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_22.5rem] lg:items-start lg:gap-6">
            {/* 휴대폰은 신청 받기 → 시간표 → 불가 시간, 넓은 화면은 오른쪽 열에 신청 받기·불가 시간 (F87) */}
            <div className="flex flex-col gap-4 max-lg:contents lg:order-2">
              <div className="max-lg:order-1">
                <AcceptingCard accepting={schedule.data.accepting_requests} />
              </div>
              <div className="max-lg:order-3">
                <PeriodList
                  periods={schedule.data.unavailable_periods}
                  editor={editor}
                  onAdd={() => setDialog({ open: true, period: null })}
                />
              </div>
            </div>
            <div className="max-lg:order-2 lg:order-1">
              <WeekCard
                monday={monday}
                now={now}
                periods={schedule.data.unavailable_periods}
                sessions={sessions.data?.items ?? []}
                editor={editor}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function dayBlocks(key: string, periods: UnavailablePeriod[], sessions: MentoringSession[]): Block[] {
  const from = dayStartMs(key);
  const to = dayStartMs(addDays(key, 1));
  const blocks: Block[] = [];
  for (const p of periods) {
    for (const range of occurrences(p, from, to)) {
      const seg = daySegment(range, key);
      if (seg)
        blocks.push({
          id: `${p.id}-${range[0]}`,
          kind: "unavailable",
          label: `${p.category ?? "불가 시간"} · ${repeatLabel(p)}`,
          start: seg[0],
          end: seg[1],
          period: p,
        });
    }
  }
  for (const s of sessions) {
    const seg = daySegment([Date.parse(s.starts_at), Date.parse(s.ends_at)], key);
    if (seg)
      blocks.push({ id: s.id, kind: "session", label: targetLabel(s), start: seg[0], end: seg[1], sessionId: s.id });
  }
  return blocks;
}

/** 지금 시각 (1분마다 갱신): 현재 시각 선 (F88) */
function useNow(initial: number): number {
  const [now, setNow] = useState(initial);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);
  return now;
}

function WeekCard({
  monday,
  now,
  periods,
  sessions,
  editor,
}: {
  monday: string;
  now: number;
  periods: UnavailablePeriod[];
  sessions: MentoringSession[];
  editor: Editor;
}) {
  const navigate = useNavigate();
  const days = weekDays(monday);
  const today = kstDateKey(new Date(now));
  const [picked, setPicked] = useState(days.includes(today) ? today : monday);
  const selected = days.includes(picked) ? picked : monday;
  const scope = useScheduleScope();
  const goTo = (target: string) =>
    scope.onWeek ? scope.onWeek(target) : void navigate({ to: "/mentor/schedule", search: { week: target } });
  const thisWeek = weekStart(today);

  return (
    <section
      aria-label="주간 일정"
      className="flex min-w-0 flex-col gap-3 rounded-xl border border-border bg-card p-4 md:p-5"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-h3 text-foreground">{weekTitle(monday)}</h2>
        <div className="flex items-center gap-3 text-caption text-muted-foreground max-md:order-last max-md:w-full md:ml-3">
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-3 w-1 rounded-full bg-destructive" />
            불가 시간
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-3 w-1 rounded-full bg-primary" />
            세션
          </span>
        </div>
        <div className="ml-auto flex items-center gap-1">
          <Button variant="outline" size="sm" disabled={monday === thisWeek} onClick={() => goTo(thisWeek)}>
            오늘
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="size-8 px-0"
            aria-label="이전 주"
            onClick={() => goTo(addDays(monday, -7))}
          >
            <ChevronLeft aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="size-8 px-0"
            aria-label="다음 주"
            onClick={() => goTo(addDays(monday, 7))}
          >
            <ChevronRight aria-hidden />
          </Button>
        </div>
      </div>
      {/* 휴대폰은 하루 보기: 요일 칩으로 날짜를 고른다 (F51) */}
      <div role="tablist" aria-label="날짜" className="flex gap-1 md:hidden">
        {days.map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={key === selected}
            aria-label={formatKst(dayStartMs(key), "M월 d일 (EEE)")}
            onClick={() => setPicked(key)}
            className={cn(
              "flex flex-1 flex-col items-center gap-1 rounded-lg py-1.5 outline-none focus-visible:ring-2 focus-visible:ring-ring",
              key === selected && "bg-sidebar-accent",
            )}
          >
            <span className={cn("text-caption", isoWeekday(key) > 5 ? "text-muted-foreground" : "text-foreground")}>
              {weekdayLabel(key)}
            </span>
            <DayNumber day={key} today={today} />
          </button>
        ))}
      </div>
      <Timetable
        days={days}
        selected={selected}
        today={today}
        now={now}
        columns={days.map((key) => dayBlocks(key, periods, sessions))}
        editor={editor}
      />
    </section>
  );
}

/** 날짜 숫자. 오늘은 primary 원 (F88) */
function DayNumber({ day, today }: { day: string; today: string }) {
  return (
    <span
      className={cn(
        "inline-flex size-7 items-center justify-center rounded-full text-body-strong",
        day === today
          ? "bg-primary text-primary-foreground"
          : isoWeekday(day) > 5
            ? "text-muted-foreground"
            : "text-foreground",
      )}
    >
      {Number(day.slice(8))}
    </span>
  );
}

/** "오전 9시", "오후 12시", "오후 1시" */
function hourLabel(h: number): string {
  if (h < 12) return `오전 ${h}시`;
  return `오후 ${h === 12 ? 12 : h - 12}시`;
}

function hhmm(minutes: number): string {
  const m = ((minutes % DAY_MINUTES) + DAY_MINUTES) % DAY_MINUTES;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

function hm(minutes: number): string {
  return hhmm(minutes).replace(/^0(?=\d:)/, "");
}

function Timetable({
  days,
  selected,
  today,
  now,
  columns,
  editor,
}: {
  days: string[];
  selected: string;
  today: string;
  now: number;
  columns: Block[][];
  editor: Editor;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const current = useNow(now);
  const nowMinutes = (current - dayStartMs(kstDateKey(new Date(current)))) / 60_000;
  // 처음에는 08:00이 맨 위에 오게 (F52)
  useLayoutEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = (el.scrollHeight * FIRST_VISIBLE_HOUR) / 24;
  }, []);
  return (
    <div className="flex flex-col">
      <div className="hidden pl-16 md:grid md:grid-cols-7">
        {days.map((key) => (
          <span key={key} className="flex flex-col items-center gap-1 pb-2">
            <span
              className={cn(
                "text-caption",
                key === today ? "text-primary-text" : isoWeekday(key) > 5 ? "text-muted-foreground" : "text-foreground",
              )}
            >
              {weekdayLabel(key)}
            </span>
            <DayNumber day={key} today={today} />
          </span>
        ))}
      </div>
      <div ref={scroller} className="h-120 overflow-y-auto border-t border-border">
        <div className="relative flex pt-2">
          <div className="w-16 shrink-0">
            {HOURS.map((h) => (
              <div key={h} className="h-12 -translate-y-2 pr-2 text-right text-caption text-muted-foreground">
                {h === 0 ? "" : hourLabel(h)}
              </div>
            ))}
          </div>
          <div className="grid flex-1 grid-cols-1 md:grid-cols-7">
            {days.map((key, i) => (
              <DayColumn
                key={key}
                day={key}
                hidden={key !== selected}
                isToday={key === today}
                nowMinutes={key === today ? nowMinutes : null}
                blocks={columns[i] ?? []}
                editor={editor}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * 하루 칸. 마우스를 빈 칸에 올리면 30분 칸에 "+ 15:00"을 보여 주고, 누르면 그 날짜·시각으로 추가 창 (F88).
 * 키보드·터치는 '등록한 불가 시간'의 [+]로 추가한다.
 */
function DayColumn({
  day,
  hidden,
  isToday,
  nowMinutes,
  blocks,
  editor,
}: {
  day: string;
  hidden: boolean;
  isToday: boolean;
  nowMinutes: number | null;
  blocks: Block[];
  editor: Editor;
}) {
  const scope = useScheduleScope();
  const [hover, setHover] = useState<number | null>(null);
  const slotAt = (e: MouseEvent<HTMLDivElement>): number | null => {
    const native = e.nativeEvent;
    const pointer = "pointerType" in native && typeof native.pointerType === "string" ? native.pointerType : "mouse";
    if (pointer !== "mouse" || scope.readOnly || e.target !== e.currentTarget) return null;
    const y = e.clientY - e.currentTarget.getBoundingClientRect().top;
    const slot = Math.floor((y / HOUR_PX) * (60 / SLOT_MINUTES)) * SLOT_MINUTES;
    return slot >= 0 && slot < DAY_MINUTES ? slot : null;
  };
  const style = (start: number, end: number): CSSProperties => ({
    top: `${(start / DAY_MINUTES) * 100}%`,
    height: `${((end - start) / DAY_MINUTES) * 100}%`,
  });
  return (
    <div
      aria-label={formatKst(dayStartMs(day), "M월 d일 (EEE)")}
      role="group"
      onPointerMove={(e) => setHover(slotAt(e))}
      onPointerLeave={() => setHover(null)}
      onClick={(e) => {
        const slot = slotAt(e);
        if (slot !== null) editor.add(day, hhmm(slot));
      }}
      className={cn(
        "relative border-l border-border",
        isToday && "bg-sidebar-accent/40",
        hidden && "max-md:hidden",
        hover !== null && "cursor-pointer",
      )}
    >
      {HOURS.map((h) => (
        <div key={h} aria-hidden className="pointer-events-none h-12 border-b border-border" />
      ))}
      {hover !== null ? (
        <div
          aria-hidden
          style={style(hover, hover + SLOT_MINUTES)}
          className="pointer-events-none absolute inset-x-0.5 flex items-center rounded-md border border-dashed border-primary/50 bg-sidebar-accent px-1.5 text-caption text-sidebar-accent-foreground"
        >
          + {hhmm(hover)}
        </div>
      ) : null}
      {blocks.map((b) => (
        <BlockView key={b.id} block={b} editor={editor} />
      ))}
      {nowMinutes !== null ? (
        <div
          aria-hidden
          style={{ top: `${(nowMinutes / DAY_MINUTES) * 100}%` }}
          className="pointer-events-none absolute inset-x-0 z-20 h-0.5 -translate-y-1/2 bg-destructive"
        >
          <span className="absolute -top-1 -left-1 size-2.5 rounded-full bg-destructive" />
        </div>
      ) : null}
    </div>
  );
}

function BlockView({ block, editor }: { block: Block; editor: Editor }) {
  const scope = useScheduleScope();
  // 하루 1,440분 중 위치 (계산 값이라 인라인 스타일)
  const style: CSSProperties = {
    top: `${(block.start / DAY_MINUTES) * 100}%`,
    height: `${((block.end - block.start) / DAY_MINUTES) * 100}%`,
  };
  // 칸이 좁아 시의 앞 0은 뺀다: "9:00–12:00"
  const time = `${hm(block.start)}–${block.end === DAY_MINUTES ? "24:00" : hm(block.end)}`;
  const short = block.end - block.start < 60;
  const className = cn(
    "absolute inset-x-0.5 z-10 flex overflow-hidden rounded-md border-l-3 py-0.5 pr-1 pl-1.5 text-left text-caption",
    short ? "flex-row items-center gap-1" : "flex-col",
    block.kind === "unavailable"
      ? "border-destructive bg-destructive-subtle text-destructive-text"
      : "border-primary bg-sidebar-accent text-sidebar-accent-foreground",
  );
  const body = (
    <>
      <span className="shrink-0 truncate text-[11px] leading-4 font-semibold tracking-tight">{time}</span>
      <span className="truncate">{block.label}</span>
    </>
  );
  // 운영진 일정 대리(F85)에는 세션 상세 화면이 아직 없어 블록만 보여 준다
  if (block.sessionId && scope.mentorId)
    return (
      <span style={style} className={className}>
        {body}
      </span>
    );
  if (block.sessionId)
    return (
      <Link
        to="/mentor/sessions/$sessionId"
        params={{ sessionId: block.sessionId }}
        aria-label={`${block.label} ${time}`}
        style={style}
        className={cn(className, "outline-none hover:brightness-95 focus-visible:ring-2 focus-visible:ring-ring")}
      >
        {body}
      </Link>
    );
  // 불가 시간 블록을 누르면 수정 창 (이미 시작한 한 번은 보기만, F53)
  const period = block.period;
  if (period && !isLocked(period, editor.now))
    return (
      <button
        type="button"
        style={style}
        aria-label={`${block.label} 수정`}
        onClick={() => editor.edit(period)}
        className={cn(className, "outline-none hover:brightness-95 focus-visible:ring-2 focus-visible:ring-ring")}
      >
        {body}
      </button>
    );
  return (
    <div style={style} className={className}>
      {body}
    </div>
  );
}

function PeriodList({ periods, editor, onAdd }: { periods: UnavailablePeriod[]; editor: Editor; onAdd: () => void }) {
  return (
    <section
      aria-labelledby="periods-title"
      className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 md:p-5"
    >
      <div className="flex items-center gap-2">
        <h2 id="periods-title" className="flex-1 text-h3 text-foreground">
          등록한 불가 시간
        </h2>
        <Button variant="outline" size="sm" className="size-8 px-0" aria-label="불가 시간 추가" onClick={onAdd}>
          <Plus aria-hidden />
        </Button>
      </div>
      {periods.length === 0 ? (
        <p className="text-body-sm text-muted-foreground">
          등록한 불가 시간이 없어요. 나머지 시간은 모두 신청을 받아요.
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-border border-t border-border">
          {periods.map((p) => (
            <li key={p.id} className="flex items-start gap-2 py-3">
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="flex items-center gap-2">
                  <span className="text-body-strong text-foreground">{p.category ?? "불가 시간"}</span>
                  <Badge variant="outline">{repeatLabel(p)}</Badge>
                </span>
                <span className="text-caption text-muted-foreground">{periodLabel(p)}</span>
                {p.reason ? <span className="text-caption text-muted-foreground">{p.reason}</span> : null}
              </span>
              {isLocked(p, editor.now) ? null : (
                <span className="flex shrink-0 gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="size-8 px-0 text-muted-foreground hover:text-foreground"
                    aria-label={`${p.category ?? "불가 시간"} 수정`}
                    onClick={() => editor.edit(p)}
                  >
                    <Pencil aria-hidden />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="size-8 px-0 text-muted-foreground hover:bg-destructive-subtle hover:text-destructive-text"
                    aria-label={`${p.category ?? "불가 시간"} 삭제`}
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
        수강생은 기수 운영시간 안에서만 신청해요. 기수마다 운영시간이 달라요.
      </p>
    </section>
  );
}
