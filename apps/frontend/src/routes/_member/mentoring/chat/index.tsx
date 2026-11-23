import { createFileRoute } from "@tanstack/react-router";

import { requireAccount } from "@/features/auth/guards";
import { threadsQuery } from "@/features/chat/api";
import { ChatPage } from "@/features/chat/components/chat-page";

/** 채팅 방 목록 (F40). 수강생·멘토 공통 */
export const Route = createFileRoute("/_member/mentoring/chat/")({
  beforeLoad: async ({ context, location }) => {
    await requireAccount(context.queryClient, ["STUDENT", "MENTOR"], location);
  },
  loader: ({ context }) => context.queryClient.prefetchInfiniteQuery(threadsQuery),
  component: () => <ChatPage />,
});
