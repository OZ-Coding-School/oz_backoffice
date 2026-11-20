import { CalendarDays, FileText, LayoutGrid, Plus, type LucideIcon } from "lucide-react";

import type { Me } from "@/features/auth/api";

export interface MemberNavItem {
  to: string;
  label: string;
  /** 태블릿 레일·하단 탭에 쓰는 짧은 이름 (F27) */
  shortLabel: string;
  icon: LucideIcon;
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

const APPLY: MemberNavItem = { to: "/mentoring/apply", label: "멘토링 신청", shortLabel: "신청", icon: Plus };

const MENTOR_NAV: MemberNavGroup[] = [{ items: [HOME] }];

export interface MemberNavOptions {
  /** '멘토링 신청' 메뉴: 1:1이나 팀을 허용하는 기수와 수강이 끝난 수강생(안내)에 (F31) */
  apply?: boolean;
}

export function memberNav(accountType: Me["account_type"], options: MemberNavOptions = {}): MemberNavGroup[] {
  if (accountType === "MENTOR") return MENTOR_NAV;
  return [
    { items: [HOME] },
    { title: "멘토링", items: options.apply ? [APPLY, REQUESTS, SESSIONS] : [REQUESTS, SESSIONS] },
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
