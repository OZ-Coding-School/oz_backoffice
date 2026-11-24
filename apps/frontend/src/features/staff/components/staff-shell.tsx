import { useQuery } from "@tanstack/react-query";
import { Link, useRouterState } from "@tanstack/react-router";
import { ChevronRight, LogOut } from "lucide-react";
import type { ReactNode } from "react";

import markDark from "@/assets/brand/oz-mark.svg";
import markLight from "@/assets/brand/oz-mark-light.svg";
import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Me } from "@/features/auth/api";
import { approvalCountQuery } from "@/features/admin-approvals/api";
import { useLogout } from "@/features/member/logout";
import { cn } from "@/lib/utils";

import { staffAccessQuery } from "../api";
import { roleLines } from "../labels";
import { currentStaffNav, staffModules, type StaffModule, type StaffNavItem } from "../nav";

/**
 * 운영진 틀 (Figma `운영진 틀 (FE-14a)`, F3·F17·F58). 데스크톱만:
 * 왼쪽 모듈 레일(72) · 모듈 메뉴(224) · 상단 막대(위치·테마). 권한이 없는 모듈·메뉴는 숨긴다
 */
export function StaffShell({ me, children }: { me: Me; children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const access = useQuery(staffAccessQuery);
  const modules = staffModules(access.data ?? { permissions: [] });
  const current = currentStaffNav(modules, pathname);
  const module = current?.module ?? modules[0];
  // 메뉴 배지: 가입 승인 대기 (F60). 그 메뉴가 보일 때만 부른다
  const showApprovals = modules.some((m) => m.items.some((i) => i.badge === "approvals"));
  const approvals = useQuery({ ...approvalCountQuery("all"), enabled: showApprovals });
  const badges: Partial<Record<NonNullable<StaffNavItem["badge"]>, number>> = { approvals: approvals.data };

  return (
    <div className="flex min-h-dvh min-w-[1280px] bg-background">
      <nav
        aria-label="모듈"
        className="sticky top-0 flex h-dvh w-18 shrink-0 flex-col items-center gap-2 border-r border-sidebar-border bg-sidebar px-2 py-3"
      >
        <Link to="/admin" aria-label="운영진 홈" className="mb-2 rounded-lg">
          <img src={markLight} alt="" className="size-10 dark:hidden" />
          <img src={markDark} alt="" className="hidden size-10 dark:block" />
        </Link>
        {modules.map((m) => (
          <ModuleLink key={m.key} module={m} active={m.key === module?.key} />
        ))}
        <div className="mt-auto">
          <UserMenu me={me} lines={roleLines(me.roles, access.data?.cohorts ?? [])} />
        </div>
      </nav>
      {module ? (
        <nav
          aria-label="메뉴"
          className="sticky top-0 flex h-dvh w-56 shrink-0 flex-col gap-1 border-r border-sidebar-border bg-sidebar px-3 py-4"
        >
          <div className="flex flex-col gap-0.5 px-2 pb-3">
            <p className="text-h3 text-foreground">{module.title ?? module.label}</p>
            <p className="text-caption text-muted-foreground">{module.description}</p>
          </div>
          {module.items.map((item) => {
            const Icon = item.icon;
            const active = item === current?.item;
            return (
              <Link
                key={item.to}
                to={item.to}
                activeOptions={{ exact: true }}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-9 items-center gap-2.5 rounded-md px-2 text-body",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/60",
                )}
              >
                <Icon aria-hidden className="size-4 shrink-0" />
                <span className="flex-1">{item.label}</span>
                {item.badge && badges[item.badge] ? (
                  <span className="inline-flex min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-caption-strong text-primary-foreground">
                    <span className="sr-only">대기 </span>
                    {(badges[item.badge] ?? 0) > 99 ? "99+" : badges[item.badge]}
                  </span>
                ) : null}
              </Link>
            );
          })}
        </nav>
      ) : null}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-15 items-center gap-2 border-b border-border bg-background px-6">
          <nav aria-label="위치" className="flex items-center gap-1.5 text-body-sm text-muted-foreground">
            {current ? (
              <>
                <span>{current.module.title ?? current.module.label}</span>
                {current.item.label !== (current.module.title ?? current.module.label) ? (
                  <>
                    <ChevronRight aria-hidden className="size-3.5" />
                    <span className="text-foreground">{current.item.label}</span>
                  </>
                ) : null}
              </>
            ) : null}
          </nav>
          <div className="flex-1" />
          <ThemeToggle />
        </header>
        <main className="flex-1 px-8 pt-8 pb-10">{children}</main>
      </div>
    </div>
  );
}

function ModuleLink({ module, active }: { module: StaffModule; active: boolean }) {
  const Icon = module.icon;
  const first = module.items[0];
  if (!first) return null;
  return (
    <Link
      to={first.to}
      // 라우터의 자동 활성 표시는 정확히 같을 때만, 하위 경로는 직접 정한다
      activeOptions={{ exact: true }}
      aria-current={active ? "true" : undefined}
      className={cn(
        "flex w-14 flex-col items-center gap-0.5 rounded-md px-1 py-1.5",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground hover:bg-sidebar-accent/60",
      )}
    >
      <Icon aria-hidden className="size-5" />
      <span className="text-caption-strong">{module.label}</span>
    </Link>
  );
}

/** 레일 아래 아바타 → 이름 · 역할(범위 이름 포함) · 로그아웃 (F58) */
function UserMenu({ me, lines }: { me: Me; lines: string[] }) {
  const onLogout = useLogout();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" aria-label="사용자 메뉴" className="inline-flex rounded-full p-1 hover:bg-muted">
          <Avatar name={me.name} />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="right" align="end">
        <DropdownMenuLabel>
          <span className="text-body-strong text-foreground">{me.name}</span>
          {lines.map((line) => (
            <span key={line} className="text-caption text-muted-foreground">
              {line}
            </span>
          ))}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onLogout}>
          <LogOut />
          로그아웃
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
