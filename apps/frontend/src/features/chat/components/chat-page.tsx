import { useQuery } from "@tanstack/react-query";
import { MessageSquare } from "lucide-react";

import { meQuery } from "@/features/auth/api";
import { cn } from "@/lib/utils";

import { Conversation } from "./conversation";
import { ThreadList } from "./thread-list";

/**
 * 채팅 (Figma `Column / 채팅 (FE-7a)`, F40). 수강생·멘토 공통.
 * 데스크톱·태블릿은 방 목록 + 대화, 휴대폰은 목록(`/mentoring/chat`) → 전체 화면 대화(`/mentoring/chat/{id}`).
 */
export function ChatPage({ threadId }: { threadId?: string }) {
  const me = useQuery(meQuery).data;
  if (!me) return null;
  return (
    <div className="flex min-h-0 flex-1">
      <div
        className={cn(
          "flex min-h-0 w-full flex-col border-border md:w-70 md:shrink-0 md:border-r lg:w-80",
          threadId && "max-md:hidden",
        )}
      >
        <ThreadList me={me} activeId={threadId} />
      </div>
      <div className={cn("min-h-0 min-w-0 flex-1 flex-col", threadId ? "flex" : "hidden md:flex")}>
        {threadId ? (
          <Conversation key={threadId} me={me} threadId={threadId} />
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center gap-1.5 p-6 text-center">
            <MessageSquare aria-hidden className="size-6 text-muted-foreground" />
            <p className="text-body-strong text-foreground">대화를 골라 주세요</p>
            <p className="text-caption text-muted-foreground">왼쪽 목록에서 방을 고르면 대화가 열려요</p>
          </div>
        )}
      </div>
    </div>
  );
}
