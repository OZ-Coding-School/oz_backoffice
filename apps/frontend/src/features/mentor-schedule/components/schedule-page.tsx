import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronLeft, ChevronRight, Ellipsis, Plus } from "lucide-react";
import { useLayoutEffect, useRef, useState, type CSSProperties } from "react";

import { ErrorState } from "@/components/error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";
import { kstDateKey } from "@/features/apply/slots";
import { targetLabel } from "@/features/mentor-sessions/labels";
import type { MentoringSession } from "@/features/sessions/api";
import { formatKst } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { scheduleQuery, weekSessionsQuery } from "../api";
import { isLocked } from "../form";
import {
  addDays,
  dayStartMs,
  daySegment,
  occurrences,
  periodLabel,
  repeatLabel,
  weekDays,
  weekdayLabel,
  weekTitle,
  type UnavailablePeriod,
} from "../schedule";
import { AcceptingCard } from "./accepting-card";
import { DeleteUnavailableDialog, UnavailableDialog } from "./unavailable-dialogs";

const DAY_MINUTES = 24 * 60;
/** 처음 보이는 시각 (F52) */
const FIRST_VISIBLE_HOUR = 8;
const HOURS = Array.from({ length: 24 }, (_, h) => h);

interface Block {
  id: string;
  kind: "unavailable" | "session";
  label: string;
  start: number; // 그날 00:00 기준 분
  end: number;
  sessionId?: string;
  period?: UnavailablePeriod;
}

/** 수정·삭제 창 열기 (F53) */
interface Editor {
  edit: (period: UnavailablePeriod) => void;
  remove: (period: UnavailablePeriod) => void;
  now: number;
}

/** 멘토 일정 (Figma `일정 · 보기 (FE-11a)`, F51·F52·A37) */
export function SchedulePage({ monday }: { monday: string }) {
  const schedule = useQuery(scheduleQuery);
  const sessions = useQuery(weekSessionsQuery(monday));
  const [now] = useState(() => Date.now());
  const [dialog, setDialog] = useState<{ open: boolean; period: UnavailablePeriod | null }>({
    open: false,
    period: null,
  });
  const [deleting, setDeleting] = useState<UnavailablePeriod | null>(null);
  const editor: Editor = {
    edit: (period) => setDialog({ open: true, period }),
    remove: setDeleting,
    now,
  };
  const today = kstDateKey(new Date(now));

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start">
        <div className="flex flex-1 flex-col gap-1">
          <h1 className="text-h1 text-foreground">일정</h1>
          <p className="text-body text-muted-foreground">
            안 되는 시간만 등록해요. 나머지 시간은 기수 운영시간 안에서 수강생이 신청할 수 있어요.
          </p>
        </div>
        <Button className="max-md:w-full" onClick={() => setDialog({ open: true, period: null })}>
          <Plus aria-hidden />
          불가 시간 추가
        </Button>
      </div>
      <UnavailableDialog
        open={dialog.open}
        period={dialog.period}
        defaultDay={weekDays(monday).includes(today) ? today : monday}
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
          <AcceptingCard accepting={schedule.data.accepting_requests} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_22.5rem] lg:items-start lg:gap-6">
            <WeekCard
              monday={monday}
              now={now}
              periods={schedule.data.unavailable_periods}
              sessions={sessions.data?.items ?? []}
              editor={editor}
            />
            <PeriodList periods={schedule.data.unavailable_periods} editor={editor} />
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
  const go = (offset: number) => void navigate({ to: "/mentor/schedule", search: { week: addDays(monday, offset) } });

  return (
    <section
      aria-label="주간 일정"
      className="flex min-w-0 flex-col gap-3 rounded-xl border border-border bg-card p-4 md:p-5"
    >
      <div className="flex items-center gap-2">
        <h2 className="flex-1 text-h3 text-foreground">{weekTitle(monday)}</h2>
        <Button variant="outline" size="sm" className="size-8 px-0" aria-label="이전 주" onClick={() => go(-7)}>
          <ChevronLeft aria-hidden />
        </Button>
        <Button variant="outline" size="sm" className="size-8 px-0" aria-label="다음 주" onClick={() => go(7)}>
          <ChevronRight aria-hidden />
        </Button>
      </div>
      <div className="flex items-center gap-4 text-caption text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="size-3 rounded-sm bg-destructive-subtle" />
          불가 시간
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="size-3 rounded-sm bg-accent" />
          세션
        </span>
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
              "flex flex-1 flex-col items-center gap-0.5 rounded-lg py-1.5 outline-none focus-visible:ring-2 focus-visible:ring-ring",
              key === selected ? "bg-accent text-primary-text" : "text-muted-foreground",
            )}
          >
            <span className="text-caption">{weekdayLabel(key)}</span>
            <span className="text-body-strong">{key.slice(8).replace(/^0/, "")}</span>
          </button>
        ))}
      </div>
      <Timetable
        days={days}
        selected={selected}
        today={today}
        columns={days.map((key) => dayBlocks(key, periods, sessions))}
        editor={editor}
      />
    </section>
  );
}

function Timetable({
  days,
  selected,
  today,
  columns,
  editor,
}: {
  days: string[];
  selected: string;
  today: string;
  columns: Block[][];
  editor: Editor;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  // 처음에는 08:00이 맨 위에 오게 (F52)
  useLayoutEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = (el.scrollHeight * FIRST_VISIBLE_HOUR) / 24;
  }, []);
  return (
    <div className="flex flex-col">
      <div className="hidden pl-12 md:grid md:grid-cols-7">
        {days.map((key) => (
          <span
            key={key}
            className={cn(
              "pb-2 text-center text-caption",
              key === today ? "text-body-strong text-primary-text" : "text-muted-foreground",
            )}
          >
            {key.slice(8).replace(/^0/, "")} {weekdayLabel(key)}
          </span>
        ))}
      </div>
      <div ref={scroller} className="h-120 overflow-y-auto border-t border-border">
        <div className="relative flex pt-2">
          <div className="w-12 shrink-0">
            {HOURS.map((h) => (
              <div key={h} className="h-12 -translate-y-2 pr-2 text-right font-mono text-caption text-muted-foreground">
                {h === 0 ? "" : `${String(h).padStart(2, "0")}:00`}
              </div>
            ))}
          </div>
          <div className="grid flex-1 grid-cols-1 md:grid-cols-7">
            {days.map((key, i) => (
              <div
                key={key}
                aria-label={formatKst(dayStartMs(key), "M월 d일 (EEE)")}
                role="group"
                className={cn("relative border-l border-border", key !== selected && "max-md:hidden")}
              >
                {HOURS.map((h) => (
                  <div key={h} className="h-12 border-b border-border" />
                ))}
                {(columns[i] ?? []).map((b) => (
                  <BlockView key={b.id} block={b} editor={editor} />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function BlockView({ block, editor }: { block: Block; editor: Editor }) {
  // 하루 1,440분 중 위치 (계산 값이라 인라인 스타일)
  const style: CSSProperties = {
    top: `${(block.start / DAY_MINUTES) * 100}%`,
    height: `${((block.end - block.start) / DAY_MINUTES) * 100}%`,
  };
  const className = cn(
    "absolute inset-x-0.5 overflow-hidden rounded-md px-1.5 py-1 text-caption",
    block.kind === "unavailable" ? "bg-destructive-subtle text-destructive-text" : "bg-accent text-primary-text",
  );
  if (block.sessionId)
    return (
      <Link
        to="/mentor/sessions/$sessionId"
        params={{ sessionId: block.sessionId }}
        style={style}
        className={cn(className, "outline-none hover:opacity-80 focus-visible:ring-2 focus-visible:ring-ring")}
      >
        {block.label}
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
        className={cn(
          className,
          "text-left outline-none hover:opacity-80 focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        {block.label}
      </button>
    );
  return (
    <div style={style} className={className}>
      {block.label}
    </div>
  );
}

function PeriodList({ periods, editor }: { periods: UnavailablePeriod[]; editor: Editor }) {
  return (
    <section
      aria-labelledby="periods-title"
      className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 md:p-5"
    >
      <h2 id="periods-title" className="text-h3 text-foreground">
        등록한 불가 시간
      </h2>
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
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="size-8 px-0"
                      aria-label={`${p.category ?? "불가 시간"} 메뉴`}
                    >
                      <Ellipsis aria-hidden />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onSelect={() => editor.edit(p)}>수정</DropdownMenuItem>
                    <DropdownMenuItem className="text-destructive-text" onSelect={() => editor.remove(p)}>
                      삭제
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
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
