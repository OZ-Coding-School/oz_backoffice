import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link, useRouterState } from "@tanstack/react-router";
import { Ellipsis, LogOut } from "lucide-react";
import { useState, type ReactNode } from "react";

import markDark from "@/assets/brand/oz-mark.svg";
import markLight from "@/assets/brand/oz-mark-light.svg";
import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { type Me } from "@/features/auth/api";
import { Logo } from "@/features/auth/components/auth-layout";
import { cn } from "@/lib/utils";

import { activeCohort, cohortLabel, enrollmentsQuery } from "../api";
import { myTeamsQuery } from "@/features/apply/api";
import { threadsQuery, unreadTotal } from "@/features/chat/api";
import { useChatStream } from "@/features/chat/stream";
import { pendingCountQuery } from "@/features/mentor-requests/api";
import { mentoringSettingsQuery } from "@/features/requests/api";

import { useLogout } from "../logout";
import {
  bottomTabLayout,
  currentNavItem,
  memberNav,
  navItems,
  pinnedTabs,
  showBottomTabs,
  type MemberNavGroup,
  type MemberNavItem,
} from "../nav";

/**
 * 수강생·멘토 공통 틀 (Figma `Column / 공통 틀 (FE-2)`, decisions F27).
 * 데스크톱(lg) 사이드바 240 · 태블릿(md) 레일 72 · 모바일 상단 막대(+ 메뉴 2개 이상이면 하단 탭).
 */
export function MemberShell({ me, children }: { me: Me; children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const student = me.account_type === "STUDENT";
  const enrollments = useQuery({ ...enrollmentsQuery, enabled: student });
  const cohort = student && enrollments.data ? activeCohort(enrollments.data) : null;
  const settings = useQuery({
    ...mentoringSettingsQuery(cohort?.enrollment.cohort_id ?? ""),
    enabled: !!cohort && !cohort.readOnly,
  });
  // 1:1이나 팀을 허용하는 기수와 수강이 끝난 수강생(안내)에 '멘토링 신청' (F31)
  const apply =
    !!cohort &&
    (cohort.readOnly || (!!settings.data && (settings.data.allow_1_on_1 || settings.data.allow_team_mentoring)));
  // 팀 멘토링 허용 기수이면서 소속 팀이 있을 때 '내 팀' (F39)
  const teams = useQuery({ ...myTeamsQuery, enabled: !!settings.data?.allow_team_mentoring });
  const team = !!settings.data?.allow_team_mentoring && (teams.data?.as_student.length ?? 0) > 0;
  const groups = memberNav(me.account_type, { apply, team });
  // 채팅 실시간 수신과 안 읽음 배지 (A58·F41)
  useChatStream(true);
  const threads = useInfiniteQuery(threadsQuery);
  // 받은 신청 승인 대기 건수 (멘토, F44)
  const pending = useQuery({ ...pendingCountQuery, enabled: me.account_type === "MENTOR" });
  const badges: Badges = { "/mentoring/chat": unreadTotal(threads.data), "/mentor/requests": pending.data };
  const current = currentNavItem(groups, pathname);
  // 채팅은 여백 없이 화면 높이를 채우고, 휴대폰 대화는 머리·하단 탭 없이 전체 화면이다 (F40)
  const fullBleed = pathname === "/mentoring/chat" || pathname.startsWith("/mentoring/chat/");
  const immersive = /^\/mentoring\/chat\/[^/]+/.test(pathname);
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
                <SidebarLink key={item.to} item={item} active={item === current} badge={badges[item.to]} />
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
          <RailLink key={item.to} item={item} active={item === current} badge={badges[item.to]} />
        ))}
      </nav>

      <div className={cn("flex min-w-0 flex-1 flex-col", fullBleed && "h-dvh")}>
        <header
          className={cn(
            "sticky top-0 z-10 flex h-14 items-center gap-2 border-b border-border bg-background px-4 md:h-15 md:px-6",
            immersive && "max-md:hidden",
          )}
        >
          <Mark className="size-8 md:hidden" />
          <p className="hidden text-body-sm text-muted-foreground md:block">{current?.label}</p>
          <div className="flex-1" />
          <ThemeToggle />
          <div className="lg:hidden">
            <UserMenu me={me} roleLine={roleLine} />
          </div>
        </header>
        {fullBleed ? (
          <main className="flex min-h-0 flex-1 flex-col">{children}</main>
        ) : (
          <main className="flex-1 px-4 pt-6 pb-8 md:px-8 md:pt-8">
            <div className="mx-auto w-full max-w-270">{children}</div>
          </main>
        )}
        {showBottomTabs(groups) ? (
          <BottomTabs
            groups={groups}
            pinned={pinnedTabs(me.account_type)}
            current={current}
            hidden={immersive}
            badges={badges}
          />
        ) : null}
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

type Badges = Partial<Record<string, number>>;

/** 메뉴 배지 숫자 (99+). 화면 읽기 프로그램에는 '<label> N'(예: 안 읽음 2)으로 읽힌다 */
function Count({ value, label, className }: { value: number | undefined; label?: string; className?: string }) {
  if (!value) return null;
  return (
    <span
      className={cn(
        "inline-flex min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-caption-strong text-primary-foreground",
        className,
      )}
    >
      <span className="sr-only">{label ?? "새 항목"} </span>
      {value > 99 ? "99+" : value}
    </span>
  );
}

function SidebarLink({ item, active, badge }: { item: MemberNavItem; active: boolean; badge?: number | undefined }) {
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
      <span className="flex-1">{item.label}</span>
      <Count value={badge} label={item.badgeLabel} />
    </Link>
  );
}

function RailLink({ item, active, badge }: { item: MemberNavItem; active: boolean; badge?: number | undefined }) {
  const Icon = item.icon;
  return (
    <Link
      to={item.to}
      aria-current={active ? "page" : undefined}
      aria-label={badge ? `${item.label} ${item.badgeLabel ?? "새 항목"} ${badge}` : item.label}
      className={cn(
        "relative flex w-14 flex-col items-center gap-0.5 rounded-md px-1 py-1.5",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground hover:bg-sidebar-accent/60",
      )}
    >
      <Icon aria-hidden className="size-5" />
      <span className="text-caption-strong">{item.shortLabel}</span>
      <Count value={badge} label={item.badgeLabel} className="absolute -top-0.5 right-0.5 min-w-4 px-1" />
    </Link>
  );
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

function BottomTabs({
  groups,
  pinned,
  current,
  hidden,
  badges,
}: {
  groups: MemberNavGroup[];
  /** 하단 탭에 먼저 둘 메뉴 (F36·F54) */
  pinned: readonly string[];
  current: MemberNavItem | undefined;
  /** 휴대폰 채팅 대화처럼 전체 화면일 때 숨긴다 (F40) */
  hidden: boolean;
  badges: Badges;
}) {
  const { tabs, more } = bottomTabLayout(groups, pinned);
  const moreItems = more.flatMap((g) => g.items).filter((i) => (badges[i.to] ?? 0) > 0);
  const moreBadge = moreItems.reduce((sum, i) => sum + (badges[i.to] ?? 0), 0);
  // 더보기 안 배지가 한 종류면 그 말로, 섞이면 '새 항목'으로 읽는다
  const moreLabels = new Set(moreItems.map((i) => i.badgeLabel));
  const moreLabel = moreLabels.size === 1 ? [...moreLabels][0] : undefined;
  const [open, setOpen] = useState(false);
  const inMore = !!current && more.some((g) => g.items.includes(current));
  const tabClass = (active: boolean) =>
    cn(
      "relative flex flex-1 flex-col items-center gap-0.5 py-2 text-caption",
      active ? "text-primary-text" : "text-muted-foreground",
    );
  return (
    <nav
      aria-label="하단 메뉴"
      className={cn(
        "sticky bottom-0 flex border-t border-border bg-background pb-[env(safe-area-inset-bottom)] md:hidden",
        hidden && "hidden",
      )}
    >
      {tabs.map((item) => {
        const Icon = item.icon;
        const active = item === current;
        return (
          <Link key={item.to} to={item.to} aria-current={active ? "page" : undefined} className={tabClass(active)}>
            <Icon aria-hidden className="size-5" />
            {item.shortLabel}
            <Count value={badges[item.to]} label={item.badgeLabel} className={TAB_BADGE} />
          </Link>
        );
      })}
      {more.length > 0 ? (
        <>
          <button
            type="button"
            aria-haspopup="dialog"
            aria-current={inMore ? "page" : undefined}
            onClick={() => setOpen(true)}
            className={tabClass(inMore)}
          >
            <Ellipsis aria-hidden className="size-5" />
            더보기
            <Count value={moreBadge} label={moreLabel} className={TAB_BADGE} />
          </button>
          <MoreSheet groups={more} current={current} open={open} onOpenChange={setOpen} badges={badges} />
        </>
      ) : null}
    </nav>
  );
}

/** 더보기 (F36): 하단 탭에 없는 메뉴를 그룹 이름과 함께 아래에서 올린다 */
const TAB_BADGE = "absolute top-1 left-1/2 ml-1.5 min-w-4 px-1";

function MoreSheet({
  groups,
  current,
  open,
  onOpenChange,
  badges,
}: {
  badges: Badges;
  groups: MemberNavGroup[];
  current: MemberNavItem | undefined;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="inset-x-0 top-auto bottom-0 mx-0 translate-y-0 rounded-b-none px-4 pt-5 pb-[calc(1.5rem+env(safe-area-inset-bottom))]">
        <DialogTitle className="text-h3 text-foreground">더보기</DialogTitle>
        <DialogDescription className="sr-only">하단 탭에 없는 메뉴</DialogDescription>
        <div className="mt-3 flex flex-col gap-3">
          {groups.map((g) => (
            <div key={g.title ?? "기본"} className="flex flex-col gap-1">
              {g.title ? <p className="px-1 text-caption text-muted-foreground">{g.title}</p> : null}
              {g.items.map((item) => {
                const Icon = item.icon;
                const active = item === current;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    onClick={() => onOpenChange(false)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center gap-2.5 rounded-md px-3 py-3 text-body-strong outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      active ? "bg-accent text-primary-text" : "text-foreground hover:bg-muted",
                    )}
                  >
                    <Icon aria-hidden className="size-4" />
                    <span className="flex-1">{item.label}</span>
                    <Count value={badges[item.to]} label={item.badgeLabel} />
                  </Link>
                );
              })}
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
