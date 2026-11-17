import { QueryClient } from "@tanstack/react-query";

import { isRetryableError } from "@/api/errors";

/** 서버 데이터의 단일 출처 (decisions F2). 앱과 테스트가 각자 새로 만든다. */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // 네트워크 오류·5xx만 한 번 더 (4xx는 같은 결과, 401은 API 클라이언트가 갱신 후 재시도, F19)
        retry: (failureCount, error) => failureCount < 1 && isRetryableError(error),
        refetchOnWindowFocus: false,
      },
    },
  });
}
