import { hasPermission, type StaffAccess } from "@/features/staff/api";

import type { ApprovalTab } from "./api";

export type SignupTab = ApprovalTab | "staff";

/** 가입 승인 탭과 보려면 필요한 권한 (F66·A86) */
export const SIGNUP_TABS: { value: SignupTab; label: string; permission: string }[] = [
  { value: "student", label: "수강생", permission: "member.approval.read" },
  { value: "mentor", label: "멘토·강사", permission: "educator.contract.read" },
  { value: "staff", label: "운영진", permission: "staff.registration.read" },
];

/** 권한이 있는 탭 (첫 탭이 기본) */
export function signupTabsFor(access: StaffAccess | undefined): SignupTab[] {
  return access ? SIGNUP_TABS.filter((t) => hasPermission(access, t.permission)).map((t) => t.value) : [];
}
