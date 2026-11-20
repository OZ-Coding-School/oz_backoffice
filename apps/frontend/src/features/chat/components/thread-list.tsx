import { useInfiniteQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { MessageSquare } from "lucide-react";

import { ErrorState } from "@/components/error-state";
import { LoadMore } from "@/components/load-more";
import { Avatar } from "@/components/ui/avatar";
import { Spinner } from "@/components/ui/spinner";
import type { Me } from "@/features/auth/api";
import { formatKst } from "@/lib/datetime";
import { cn } from "@/lib/utils";

import { threadsQuery } from "../api";
import { preview, threadKindLabel, threadTitle } from "../labels";

/** 방 목록 (Figma `Screen / 채팅`, F40·A74). 새 대화 버튼은 없다 */
export function ThreadList({ me, activeId }: { me: Me; activeId: string | undefined }) {
  const list = useInfiniteQuery(threadsQuery);
  const threads = list.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <section aria-labelledby="chat-threads" className="flex min-h-0 flex-col">
      <h1 id="chat-threads" className="px-4 py-4 text-h3 text-foreground md:px-5">
        채팅
      </h1>
      {list.isPending ? (
        <div className="flex justify-center py-6">
          <Spinner />
        </div>
      ) : list.isError ? (
        <ErrorState onRetry={() => void list.refetch()} />
      ) : threads.length === 0 ? (
        <div className="flex flex-col items-center gap-1.5 px-6 py-16 text-center">
          <MessageSquare aria-hidden className="size-6 text-muted-foreground" />
          <p className="text-body-strong text-foreground">아직 대화가 없어요</p>
          <p className="text-caption text-muted-foreground">멘토링을 신청하면 멘토와 대화할 수 있어요</p>
        </div>
      ) : (
        <ul className="min-h-0 flex-1 overflow-y-auto">
          {threads.map((t) => {
            const title = threadTitle(t, me.account_type);
            const active = t.id === activeId;
            return (
              <li key={t.id}>
                <Link
                  to="/mentoring/chat/$threadId"
                  params={{ threadId: t.id }}
                  aria-current={active ? "page" : undefined}
                  aria-label={`${title}${t.unread_count ? ` · 안 읽음 ${t.unread_count}` : ""}`}
                  className={cn(
                    "flex items-start gap-3 px-4 py-3 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset md:px-5",
                    active ? "bg-accent" : "hover:bg-muted",
                  )}
                >
                  <Avatar name={t.kind === "TEAM" ? (t.team_label ?? "팀") : title} />
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="flex items-center gap-2">
                      <span className="flex-1 truncate text-body-strong text-foreground">{title}</span>
                      {t.last_message_at ? (
                        <span className="shrink-0 text-caption text-muted-foreground">
                          {formatKst(t.last_message_at, "MM/dd")}
                        </span>
                      ) : null}
                    </span>
                    {me.account_type === "MENTOR" ? (
                      <span className="text-caption text-muted-foreground">{threadKindLabel(t)}</span>
                    ) : null}
                    <span className="flex items-center gap-2">
                      <span className="flex-1 truncate text-caption text-muted-foreground">{preview(t)}</span>
                      {t.unread_count ? (
                        <span
                          aria-hidden
                          className="inline-flex min-w-5 shrink-0 justify-center rounded-full bg-primary px-1.5 text-caption-strong text-primary-foreground"
                        >
                          {t.unread_count}
                        </span>
                      ) : null}
                    </span>
                  </span>
                </Link>
              </li>
            );
          })}
          {list.hasNextPage ? (
            <li>
              <LoadMore
                loading={list.isFetchingNextPage}
                label="방을 더 불러오는 중…"
                onVisible={() => void list.fetchNextPage()}
              />
            </li>
          ) : null}
        </ul>
      )}
    </section>
  );
}
