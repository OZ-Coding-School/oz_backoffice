import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { LogOut } from "lucide-react";
import type { ReactNode } from "react";

import markDark from "@/assets/brand/oz-mark.svg";
import markLight from "@/assets/brand/oz-mark-light.svg";
import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { logout, type Me } from "@/features/auth/api";
import { Logo } from "@/features/auth/components/auth-layout";
import { cn } from "@/lib/utils";

import { activeCohort, cohortLabel, enrollmentsQuery } from "../api";
import { currentNavItem, memberNav, navItems, showBottomTabs, type MemberNavItem } from "../nav";

/**
 * 수강생·멘토 공통 틀 (Figma `Column / 공통 틀 (FE-2)`, decisions F27).
 * 데스크톱(lg) 사이드바 240 · 태블릿(md) 레일 72 · 모바일 상단 막대(+ 메뉴 2개 이상이면 하단 탭).
 */
export function MemberShell({ me, children }: { me: Me; children: ReactNode }) {
  const groups = memberNav(me.account_type);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const current = currentNavItem(groups, pathname);
  const student = me.account_type === "STUDENT";
  const enrollments = useQuery({ ...enrollmentsQuery, enabled: student });
  const cohort = student && enrollments.data ? activeCohort(enrollments.data) : null;
  const roleLine = student ? (cohort ? `수강생 · ${cohortLabel(cohort.enrollment)}` : "수강생") : "멘토";

  return (
    <div className="flex min-h-dvh bg-background">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col gap-4 border-r border-sidebar-border bg-sidebar p-3 lg:flex">
        <Logo size="sm" className="px-2 pt-2" />
        <nav aria-label="메뉴" className="flex flex-col gap-3">
          {groups.map((group, index) => (
            <div key={group.title ?? index} className="flex flex-col gap-0.5">
              {group.title ? <p className="px-2 py-1.5 text-caption text-muted-foreground">{group.title}</p> : null}
              {group.items.map((item) => (
                <SidebarLink key={item.to} item={item} active={item === current} />
              ))}
            </div>
          ))}
        </nav>
        <div className="mt-auto flex items-center gap-2.5 border-t border-sidebar-border px-2 pt-3">
          <Avatar name={me.name} />
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-body-strong text-foreground">{me.name}</span>
            <span title={roleLine} className="truncate text-caption text-muted-foreground">
              {roleLine}
            </span>
          </div>
          <LogoutButton />
        </div>
      </aside>

      <nav
        aria-label="메뉴"
        className="sticky top-0 hidden h-dvh w-18 shrink-0 flex-col items-center gap-4 border-r border-sidebar-border bg-sidebar px-2 py-3 md:flex lg:hidden"
      >
        <Mark className="size-10" />
        {navItems(groups).map((item) => (
          <RailLink key={item.to} item={item} active={item === current} />
        ))}
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-14 items-center gap-2 border-b border-border bg-background px-4 md:h-15 md:px-6">
          <Mark className="size-8 md:hidden" />
          <p className="hidden text-body-sm text-muted-foreground md:block">{current?.label}</p>
          <div className="flex-1" />
          <ThemeToggle />
          <div className="lg:hidden">
            <UserMenu me={me} roleLine={roleLine} />
          </div>
        </header>
        <main className="flex-1 px-4 pt-6 pb-8 md:px-8 md:pt-8">
          <div className="mx-auto w-full max-w-270">{children}</div>
        </main>
        {showBottomTabs(groups) ? <BottomTabs items={navItems(groups)} current={current} /> : null}
      </div>
    </div>
  );
}

function Mark({ className }: { className?: string }) {
  return (
    <>
      <img src={markLight} alt="오즈코딩스쿨" className={cn("dark:hidden", className)} />
      <img src={markDark} alt="오즈코딩스쿨" className={cn("hidden dark:block", className)} />
    </>
  );
}

function SidebarLink({ item, active }: { item: MemberNavItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      to={item.to}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex h-9 items-center gap-2.5 rounded-md px-2 text-body",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground hover:bg-sidebar-accent/60",
      )}
    >
      <Icon aria-hidden className="size-4 shrink-0" />
      {item.label}
    </Link>
  );
}

function RailLink({ item, active }: { item: MemberNavItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      to={item.to}
      aria-current={active ? "page" : undefined}
      aria-label={item.label}
      className={cn(
        "flex w-14 flex-col items-center gap-0.5 rounded-md px-1 py-1.5",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground hover:bg-sidebar-accent/60",
      )}
    >
      <Icon aria-hidden className="size-5" />
      <span className="text-caption-strong">{item.shortLabel}</span>
    </Link>
  );
}

function useLogout() {
  const navigate = useNavigate();
  return async () => {
    await logout();
    await navigate({ to: "/login", replace: true });
  };
}

function LogoutButton() {
  const onLogout = useLogout();
  return (
    <Button variant="ghost" size="sm" className="px-2" aria-label="로그아웃" onClick={onLogout}>
      <LogOut />
    </Button>
  );
}

/** 모바일·태블릿 사용자 메뉴: 아바타 → 이름 · 역할·기수 · 로그아웃 (F27) */
function UserMenu({ me, roleLine }: { me: Me; roleLine: string }) {
  const onLogout = useLogout();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" aria-label="사용자 메뉴" className="inline-flex rounded-full p-1 hover:bg-muted">
          <Avatar name={me.name} size="sm" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>
          <span className="text-body-strong text-foreground">{me.name}</span>
          <span className="text-caption text-muted-foreground">{roleLine}</span>
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

function BottomTabs({ items, current }: { items: MemberNavItem[]; current: MemberNavItem | undefined }) {
  return (
    <nav
      aria-label="하단 메뉴"
      className="sticky bottom-0 flex border-t border-border bg-background pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {items.map((item) => {
        const Icon = item.icon;
        const active = item === current;
        return (
          <Link
            key={item.to}
            to={item.to}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex flex-1 flex-col items-center gap-0.5 py-2 text-caption",
              active ? "text-primary-text" : "text-muted-foreground",
            )}
          >
            <Icon aria-hidden className="size-5" />
            {item.shortLabel}
          </Link>
        );
      })}
    </nav>
  );
}
