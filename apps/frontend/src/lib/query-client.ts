import { QueryClient } from '@tanstack/react-query'

/** 서버 데이터의 단일 출처 (decisions F2). 앱과 테스트가 각자 새로 만든다. */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  })
}
