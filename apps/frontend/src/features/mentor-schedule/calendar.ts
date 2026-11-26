import { kstDateKey } from "@/features/apply/slots";
import { targetLabel } from "@/features/mentor-sessions/labels";
import type { MentoringSession } from "@/features/sessions/api";
import { formatKst } from "@/lib/datetime";

import { addDays, dayStartMs, occurrences, repeatLabel, type UnavailablePeriod } from "./schedule";

/** 하루 칸에 보이는 줄 수 (F89) */
export const MAX_LANES = 3;

/** 월 달력의 일정 하나 (그날 한 칸) */
export interface CalendarEvent {
  /** 날짜까지 포함한 고유 값 */
  id: string;
  /** 이웃한 날과 이어 그릴 기준: 같은 개인 일정(period id)이면 잇는다. 세션은 잇지 않는다 */
  chain: string | null;
  kind: "personal" | "session";
  start: number;
  /** "9:00" / "하루 종일" */
  time: string;
  label: string;
  period?: UnavailablePeriod;
  session?: MentoringSession;
}

function hm(ms: number): string {
  return formatKst(ms, "H:mm");
}

export function personalLabel(p: UnavailablePeriod): string {
  const name = p.category ?? "개인 일정";
  return p.repeat === "ONCE" ? name : `${name} · ${repeatLabel(p)}`;
}

/**
 * 그날 칸의 일정 (시작 순). 시각이 있는 회차는 시작한 날에만, 하루 종일은 걸친 날마다 넣는다.
 */
export function dayEvents(day: string, periods: UnavailablePeriod[], sessions: MentoringSession[]): CalendarEvent[] {
  const from = dayStartMs(day);
  const to = dayStartMs(addDays(day, 1));
  const events: CalendarEvent[] = [];
  for (const p of periods) {
    for (const [s] of occurrences(p, from, to)) {
      if (!p.all_day && (s < from || s >= to)) continue;
      events.push({
        id: `${p.id}-${day}`,
        chain: p.id,
        kind: "personal",
        start: p.all_day ? from : s,
        time: p.all_day ? "하루 종일" : hm(s),
        label: personalLabel(p),
        period: p,
      });
    }
  }
  for (const s of sessions) {
    const start = Date.parse(s.starts_at);
    if (kstDateKey(new Date(start)) !== day) continue;
    events.push({ id: s.id, chain: null, kind: "session", start, time: hm(start), label: targetLabel(s), session: s });
  }
  return events.sort((a, b) => a.start - b.start || a.label.localeCompare(b.label));
}

/** 한 주 줄에 그릴 막대: 같은 개인 일정이 이어지는 날은 한 막대 */
export interface Segment {
  event: CalendarEvent;
  /** 0(월) ~ 6(일) */
  from: number;
  to: number;
  lane: number;
}

/**
 * 한 주(7칸)의 막대와 칸마다 숨은 일정 수 (F89). 이어진 막대는 그 주 안에서 같은 줄을 지킨다.
 * 앞선 칸에서 시작한 막대 → 긴 막대 → 이른 시각 순으로 줄을 채운다.
 */
export function weekSegments(columns: CalendarEvent[][]): { segments: Segment[]; hidden: number[] } {
  const segments: Segment[] = [];
  const open = new Map<string, Segment>();
  columns.forEach((events, col) => {
    const seen = new Set<string>();
    for (const event of events) {
      const chained = event.chain ? open.get(event.chain) : undefined;
      if (event.chain && chained && chained.to === col - 1) {
        chained.to = col;
      } else {
        const seg = { event, from: col, to: col, lane: -1 };
        segments.push(seg);
        if (event.chain) open.set(event.chain, seg);
      }
      if (event.chain) seen.add(event.chain);
    }
    for (const key of [...open.keys()]) if (!seen.has(key)) open.delete(key);
  });
  const timeOfDay = (s: Segment) =>
    s.event.time === "하루 종일" ? -1 : s.event.start - dayStartMs(kstDateKey(new Date(s.event.start)));
  segments.sort((a, b) => a.from - b.from || b.to - b.from - (a.to - a.from) || timeOfDay(a) - timeOfDay(b));
  const lanes: Segment[][] = [];
  for (const seg of segments) {
    let lane = 0;
    while (lanes[lane]?.some((o) => !(o.to < seg.from || o.from > seg.to))) lane += 1;
    (lanes[lane] ??= []).push(seg);
    seg.lane = lane;
  }
  const hidden = columns.map(
    (events, col) => events.length - segments.filter((s) => s.lane < MAX_LANES && s.from <= col && col <= s.to).length,
  );
  return { segments, hidden };
}
