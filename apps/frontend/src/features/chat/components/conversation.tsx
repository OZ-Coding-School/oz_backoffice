import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, MessageSquareOff } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { toast } from "sonner";

import { ApiError } from "@/api/errors";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LoadMore } from "@/components/load-more";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { Me } from "@/features/auth/api";
import { cn } from "@/lib/utils";

import {
  chronological,
  MESSAGE_MAX_LENGTH,
  messagesQuery,
  threadQuery,
  useMarkRead,
  useSendMessage,
  type ChatMessage,
} from "../api";
import { isMine, messageTime, threadKindLabel, threadTitle } from "../labels";
import { DeleteMessageDialog } from "./delete-message-dialog";

const NEAR_BOTTOM_PX = 48;

/** 대화 (Figma `Screen / 채팅 · 대화`, F40·A57) */
export function Conversation({ me, threadId }: { me: Me; threadId: string }) {
  const thread = useQuery(threadQuery(threadId));
  const messages = useInfiniteQuery(messagesQuery(threadId));
  const items = chronological(messages.data);
  const markRead = useMarkRead(threadId);
  const scroller = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const keep = useRef<{ height: number; top: number } | null>(null);
  const lastRead = useRef<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<ChatMessage | null>(null);
  const newest = items.at(-1)?.id;
  const unread = thread.data?.unread_count ?? 0;

  // 이전 메시지를 위에 붙여도 보던 자리를 지키고, 맨 아래였으면 새 메시지를 따라 내려간다
  const count = items.length;
  useLayoutEffect(() => {
    const el = scroller.current;
    if (!el || count === 0 || !newest) return;
    if (keep.current) {
      el.scrollTop = el.scrollHeight - keep.current.height + keep.current.top;
      keep.current = null;
    } else if (atBottom.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [count, newest]);

  // 마지막 메시지까지 보면 읽음 (A57)
  const readIfAtBottom = () => {
    if (!newest || !atBottom.current || unread === 0 || lastRead.current === newest) return;
    lastRead.current = newest;
    markRead.mutate(newest);
  };
  useEffect(readIfAtBottom);

  const onScroll = () => {
    const el = scroller.current;
    if (!el) return;
    atBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
    readIfAtBottom();
  };

  const loadOlder = () => {
    const el = scroller.current;
    if (el) keep.current = { height: el.scrollHeight, top: el.scrollTop };
    void messages.fetchNextPage();
  };

  if (thread.isError) {
    return thread.error instanceof ApiError && thread.error.status === 404 ? (
      <div className="flex flex-1 items-center justify-center p-6">
        <EmptyState
          icon={MessageSquareOff}
          title="채팅방을 찾을 수 없어요"
          description="대화할 수 없는 방이에요. 목록에서 다시 골라 주세요."
        />
      </div>
    ) : (
      <ErrorState onRetry={() => void thread.refetch()} />
    );
  }

  const title = thread.data ? threadTitle(thread.data, me.account_type) : "";
  return (
    <section aria-label={title || "대화"} className="flex min-h-0 flex-1 flex-col">
      <header className="flex h-15 shrink-0 items-center gap-2.5 border-b border-border px-3 md:px-5">
        <Button asChild variant="ghost" size="sm" className="size-9 px-0 md:hidden">
          <Link to="/mentoring/chat" aria-label="방 목록">
            <ArrowLeft aria-hidden />
          </Link>
        </Button>
        {thread.data ? (
          <>
            <Avatar name={thread.data.kind === "TEAM" ? (thread.data.team_label ?? "팀") : title} size="sm" />
            <div className="flex min-w-0 flex-col">
              <h2 className="truncate text-body-strong text-foreground">{title}</h2>
              {me.account_type === "MENTOR" ? (
                <span className="text-caption text-muted-foreground">{threadKindLabel(thread.data)}</span>
              ) : null}
            </div>
          </>
        ) : null}
      </header>
      <div
        ref={scroller}
        onScroll={onScroll}
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4 md:px-6"
      >
        {messages.hasNextPage ? (
          <LoadMore loading={messages.isFetchingNextPage} label="이전 메시지를 불러오는 중…" onVisible={loadOlder} />
        ) : null}
        {messages.isPending ? (
          <div className="flex flex-1 items-center justify-center">
            <Spinner />
          </div>
        ) : messages.isError ? (
          <ErrorState onRetry={() => void messages.refetch()} />
        ) : (
          <ol className="flex flex-col gap-3">
            {items.map((m) => (
              <li key={m.id}>
                <MessageItem
                  message={m}
                  mine={isMine(m, me)}
                  selected={selected === m.id}
                  onSelect={() => setSelected(m.id)}
                  onDelete={() => setDeleting(m)}
                />
              </li>
            ))}
          </ol>
        )}
      </div>
      <Composer
        threadId={threadId}
        onSent={() => {
          atBottom.current = true;
        }}
      />
      <DeleteMessageDialog threadId={threadId} message={deleting} onClose={() => setDeleting(null)} />
    </section>
  );
}

function MessageItem({
  message,
  mine,
  selected,
  onSelect,
  onDelete,
}: {
  message: ChatMessage;
  mine: boolean;
  selected: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  if (message.sender_kind === "SYSTEM") {
    return (
      <p className="mx-auto w-fit max-w-full rounded-full bg-muted px-3 py-1.5 text-center text-caption text-muted-foreground">
        {message.body}
      </p>
    );
  }
  const canDelete = mine && !message.is_deleted;
  return (
    <div className={cn("group flex flex-col gap-1", mine ? "items-end" : "items-start")}>
      <span className="text-caption text-muted-foreground">
        {mine ? "나" : message.sender_name} · {messageTime(message)}
      </span>
      <div className="flex max-w-[85%] items-center gap-2 md:max-w-[70%]">
        {canDelete ? (
          <button
            type="button"
            onClick={onDelete}
            aria-label="메시지 삭제"
            className={cn(
              "shrink-0 rounded-md border border-border bg-background px-2 py-1 text-caption text-destructive-text outline-none focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-ring md:opacity-0 md:group-hover:opacity-100",
              selected ? "inline-flex" : "max-md:hidden",
            )}
          >
            삭제
          </button>
        ) : null}
        <p
          // 휴대폰은 길게 누르면(contextmenu) 삭제 버튼을 보여 준다
          onContextMenu={(e) => {
            if (!canDelete) return;
            e.preventDefault();
            onSelect();
          }}
          className={cn(
            "rounded-2xl px-4 py-2.5 text-body break-words whitespace-pre-wrap",
            message.is_deleted
              ? "bg-muted text-muted-foreground"
              : mine
                ? "bg-primary text-primary-foreground"
                : "border border-border bg-card text-foreground",
          )}
        >
          {message.is_deleted ? "삭제된 메시지입니다." : message.body}
        </p>
      </div>
    </div>
  );
}

function prefersButtonSend(): boolean {
  // 휴대폰은 Enter가 줄바꿈이고 버튼으로 보낸다 (F40)
  return typeof window.matchMedia === "function" && window.matchMedia("(max-width: 767px)").matches;
}

function Composer({ threadId, onSent }: { threadId: string; onSent: () => void }) {
  const [value, setValue] = useState("");
  const [buttonOnly] = useState(prefersButtonSend);
  const send = useSendMessage(threadId);
  const text = value.trim();

  const submit = async () => {
    if (!text || send.isPending) return;
    try {
      await send.mutateAsync(text);
      setValue("");
      onSent();
    } catch {
      toast.error("메시지를 보내지 못했어요. 잠시 후 다시 보내 주세요.");
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== "Enter" || e.shiftKey || e.nativeEvent.isComposing || prefersButtonSend()) return;
    e.preventDefault();
    void submit();
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
      className="flex shrink-0 items-end gap-2 border-t border-border px-3 py-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] md:px-5"
    >
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <textarea
          aria-label="메시지"
          rows={1}
          value={value}
          maxLength={MESSAGE_MAX_LENGTH}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={buttonOnly ? "메시지 입력" : "메시지를 입력하세요 (Enter 전송, Shift+Enter 줄바꿈)"}
          className="max-h-40 min-h-10 resize-none rounded-md border border-input bg-background px-3 py-2 text-body text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring [field-sizing:content]"
        />
        {value.length > 0 ? (
          <span className="self-end text-caption text-muted-foreground">
            {value.length.toLocaleString()} / {MESSAGE_MAX_LENGTH.toLocaleString()}
          </span>
        ) : null}
      </div>
      <Button type="submit" disabled={!text || send.isPending} className="h-10">
        보내기
      </Button>
    </form>
  );
}
