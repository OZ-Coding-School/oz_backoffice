import { LayoutGrid, type LucideIcon } from "lucide-react";

import { hasPermission, type StaffAccess } from "./api";

export interface StaffNavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** 이 권한이 있어야 보인다 (없으면 모두) */
  permission?: string;
}

export interface StaffModule {
  key: string;
  label: string;
  /** 모듈 메뉴 제목 아래 설명 */
  description: string;
  icon: LucideIcon;
  items: StaffNavItem[];
}

/**
 * 운영진 모듈 (F3·F58): 만든 화면만 넣고 PR마다 모듈·메뉴를 더한다.
 * 범위 밖 모듈(출결 감시·행정 업무·디스코드)은 넣지 않는다 (F15).
 */
const MODULES: StaffModule[] = [
  {
    key: "home",
    label: "홈",
    description: "운영진 홈",
    icon: LayoutGrid,
    items: [{ to: "/admin", label: "홈", icon: LayoutGrid }],
  },
];

/** 권한으로 거른 모듈 (메뉴가 하나도 없는 모듈은 뺀다, F17) */
export function staffModules(access: Pick<StaffAccess, "permissions">): StaffModule[] {
  return MODULES.map((m) => ({
    ...m,
    items: m.items.filter((item) => !item.permission || hasPermission(access, item.permission)),
  })).filter((m) => m.items.length > 0);
}

/** 지금 주소의 모듈·메뉴: 가장 길게 맞는 메뉴 (하위 경로 포함) */
export function currentStaffNav(
  modules: readonly StaffModule[],
  pathname: string,
): { module: StaffModule; item: StaffNavItem } | undefined {
  let best: { module: StaffModule; item: StaffNavItem } | undefined;
  for (const module of modules)
    for (const item of module.items) {
      const match = pathname === item.to || pathname.startsWith(`${item.to}/`);
      if (match && (!best || item.to.length > best.item.to.length)) best = { module, item };
    }
  return best;
}
