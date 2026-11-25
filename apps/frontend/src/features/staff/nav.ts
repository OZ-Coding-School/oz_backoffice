import {
  BadgeCheck,
  Building2,
  KeyRound,
  Network,
  LayoutGrid,
  ShieldCheck,
  UserCheck,
  Users,
  type LucideIcon,
} from "lucide-react";

import { hasPermission, type StaffAccess } from "./api";

export interface StaffNavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** 이 권한 중 하나라도 있어야 보인다 (없으면 모두) */
  permissions?: string[];
  /** 메뉴 배지 (대기 건수) */
  badge?: "approvals";
}

export interface StaffModule {
  key: string;
  /** 레일의 짧은 이름 */
  label: string;
  /** 모듈 메뉴 제목·위치 (없으면 label) */
  title?: string;
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
  {
    key: "members",
    label: "회원",
    title: "회원 관리",
    description: "회원 가입 승인",
    icon: ShieldCheck,
    items: [
      {
        to: "/admin/members/approvals",
        label: "가입 승인",
        icon: UserCheck,
        // 수강생 · 멘토·강사 · 운영진 탭 (A33·A86·F66). 배지는 세 탭 대기 합
        permissions: ["member.approval.read", "educator.contract.read", "staff.registration.read"],
        badge: "approvals",
      },
    ],
  },
  {
    key: "org",
    label: "조직",
    title: "조직 설정",
    description: "부서·직위·직원·권한",
    icon: Building2,
    // F64·F69·F70: 부서·직위·직원·권한
    items: [
      {
        to: "/admin/org/departments",
        label: "부서",
        icon: Network,
        permissions: ["org.department.read"],
      },
      {
        to: "/admin/org/positions",
        label: "직위",
        icon: BadgeCheck,
        permissions: ["org.position.read"],
      },
      {
        to: "/admin/org/employees",
        label: "직원",
        icon: Users,
        // 직원 조회 또는 담당자 조회 (A83·A86·F67)
        permissions: ["org.employee.read", "staff.assignment.read"],
      },
      {
        to: "/admin/org/permissions",
        label: "권한",
        icon: KeyRound,
        permissions: ["access.role.read"],
      },
    ],
  },
];

/** 권한으로 거른 모듈 (메뉴가 하나도 없는 모듈은 뺀다, F17) */
export function staffModules(access: Pick<StaffAccess, "permissions">): StaffModule[] {
  return MODULES.map((m) => ({
    ...m,
    items: m.items.filter((item) => !item.permissions || item.permissions.some((code) => hasPermission(access, code))),
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
