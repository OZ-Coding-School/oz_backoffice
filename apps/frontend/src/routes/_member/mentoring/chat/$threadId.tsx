import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { messagesQuery, threadQuery, threadsQuery } from "@/features/chat/api";
import { ChatPage } from "@/features/chat/components/chat-page";

/** 채팅 대화 (F40) */
export const Route = createFileRoute("/_member/mentoring/chat/$threadId")({
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["STUDENT", "MENTOR"], location);
  },
  loader: ({ context, params }) =>
    Promise.all([
      context.queryClient.prefetchInfiniteQuery(threadsQuery),
      context.queryClient.prefetchQuery(threadQuery(params.threadId)),
      context.queryClient.prefetchInfiniteQuery(messagesQuery(params.threadId)),
    ]),
  component: function ChatThread() {
    const { threadId } = Route.useParams();
    return <ChatPage threadId={threadId} />;
  },
});
