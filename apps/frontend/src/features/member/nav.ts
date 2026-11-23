import {
  CalendarDays,
  FileText,
  LayoutGrid,
  MessageSquare,
  Plus,
  User,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";

import type { Me } from "@/features/auth/api";

export interface MemberNavItem {
  to: string;
  label: string;
  /** 태블릿 레일·하단 탭에 쓰는 짧은 이름 (F27) */
  shortLabel: string;
  icon: LucideIcon;
  /** 메뉴 배지 숫자를 화면 읽기 프로그램에 읽어 줄 말 (채팅 '안 읽음' F41, 받은 신청 '대기' F44) */
  badgeLabel?: string;
}

export interface MemberNavGroup {
  /** 없으면 그룹 이름 없이 맨 위 (홈) */
  title?: string;
  items: MemberNavItem[];
}

const HOME: MemberNavItem = { to: "/", label: "홈", shortLabel: "홈", icon: LayoutGrid };

/**
 * 회원 메뉴 (F27): 이미 만든 화면만 넣는다. 화면 PR마다 해당 그룹에 메뉴를 추가한다.
 * 범위 밖(헬프센터·내 문서함·알림)은 넣지 않는다 (F15).
 */
const REQUESTS: MemberNavItem = {
  to: "/mentoring/requests",
  label: "신청 내역",
  shortLabel: "신청 내역",
  icon: FileText,
};

const SESSIONS: MemberNavItem = {
  to: "/mentoring/sessions",
  label: "진행 기록",
  shortLabel: "진행 기록",
  icon: CalendarDays,
};

const TEAM: MemberNavItem = { to: "/mentoring/team", label: "내 팀", shortLabel: "내 팀", icon: Users };

const CHAT: MemberNavItem = {
  to: "/mentoring/chat",
  label: "채팅",
  shortLabel: "채팅",
  icon: MessageSquare,
  badgeLabel: "안 읽음",
};

const BALANCES: MemberNavItem = {
  to: "/mentoring/balances",
  label: "시간 지급·차감 내역",
  shortLabel: "시간 내역",
  icon: Wallet,
};

const PROFILE: MemberNavItem = { to: "/my/profile", label: "내 정보", shortLabel: "내 정보", icon: User };

const APPLY: MemberNavItem = { to: "/mentoring/apply", label: "멘토링 신청", shortLabel: "신청", icon: Plus };

const RECEIVED: MemberNavItem = {
  to: "/mentor/requests",
  label: "받은 신청",
  shortLabel: "받은 신청",
  icon: FileText,
  badgeLabel: "대기",
};

const MENTOR_NAV: MemberNavGroup[] = [{ items: [HOME] }, { title: "멘토링", items: [RECEIVED, CHAT] }];

export interface MemberNavOptions {
  /** '멘토링 신청' 메뉴: 1:1이나 팀을 허용하는 기수와 수강이 끝난 수강생(안내)에 (F31) */
  apply?: boolean;
  /** '내 팀' 메뉴: 팀 멘토링 허용 기수이면서 소속 팀이 있을 때 (F39) */
  team?: boolean;
}

export function memberNav(accountType: Me["account_type"], options: MemberNavOptions = {}): MemberNavGroup[] {
  if (accountType === "MENTOR") return MENTOR_NAV;
  return [
    { items: [HOME] },
    {
      title: "멘토링",
      items: [...(options.apply ? [APPLY] : []), REQUESTS, SESSIONS, ...(options.team ? [TEAM] : []), CHAT, BALANCES],
    },
    { title: "내 공간", items: [PROFILE] },
  ];
}

export function navItems(groups: readonly MemberNavGroup[]): MemberNavItem[] {
  return groups.flatMap((g) => g.items);
}

/** 모바일 하단 탭은 메뉴가 2개 이상일 때만 보인다 (F27) */
export function showBottomTabs(groups: readonly MemberNavGroup[]): boolean {
  return navItems(groups).length >= 2;
}

/** 지금 경로의 메뉴 (상단 막대 위치 표시). 하위 경로는 가장 긴 접두어로 찾는다 */
export function currentNavItem(groups: readonly MemberNavGroup[], pathname: string): MemberNavItem | undefined {
  return navItems(groups)
    .filter((item) => (item.to === "/" ? pathname === "/" : pathname === item.to || pathname.startsWith(`${item.to}/`)))
    .sort((a, b) => b.to.length - a.to.length)[0];
}

/** 하단 탭에 바로 둘 수 있는 메뉴 수. 넘으면 앞 4개 + 더보기 (F36) */
export const MAX_BOTTOM_TABS = 5;
const PINNED_TABS = ["/", "/mentoring/apply", "/mentoring/sessions", "/mentoring/requests"];

export interface BottomTabLayout {
  tabs: MemberNavItem[];
  /** 더보기에 들어갈 메뉴 (그룹 이름 유지). 없으면 더보기 탭이 없다 */
  more: MemberNavGroup[];
}

/**
 * 하단 탭 (F36): 메뉴가 5개 이하면 모두, 넘으면 홈·신청·진행 기록·신청 내역(있는 것) 4개 + 더보기.
 * 고정 메뉴가 4개보다 적으면 사이드바 순서대로 채운다.
 */
export function bottomTabLayout(groups: readonly MemberNavGroup[]): BottomTabLayout {
  const items = navItems(groups);
  if (items.length <= MAX_BOTTOM_TABS) return { tabs: items, more: [] };
  const pinned = PINNED_TABS.map((to) => items.find((i) => i.to === to)).filter((i): i is MemberNavItem => !!i);
  const tabs = [...pinned, ...items.filter((i) => !pinned.includes(i))].slice(0, MAX_BOTTOM_TABS - 1);
  const more = groups
    .map((g) => ({ ...g, items: g.items.filter((i) => !tabs.includes(i)) }))
    .filter((g) => g.items.length > 0);
  return { tabs, more };
}
