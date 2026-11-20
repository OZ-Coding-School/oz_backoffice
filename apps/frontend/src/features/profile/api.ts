import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema.gen";

export type PasswordChangeStatus = components["schemas"]["PasswordChangeStatusResponse"];

export const profileKeys = {
  passwordChange: ["profile", "password-change"] as const,
};

/** 비밀번호 변경 상태 (A72): 링크를 보낸 뒤 창이 열려 있는 동안 5초마다 다시 본다 */
export const POLL_MS = 5_000;

export const passwordChangeQuery = queryOptions({
  queryKey: profileKeys.passwordChange,
  queryFn: () => unwrap(api.GET("/api/v1/me/password-change")),
});

export function useSendPasswordLink() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/me/password-change/link")),
    onSuccess: (status) => queryClient.setQueryData(profileKeys.passwordChange, status),
  });
}

export function useChangePassword() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (newPassword: string) =>
      unwrap(api.POST("/api/v1/me/password-change", { body: { new_password: newPassword } })),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: profileKeys.passwordChange }),
  });
}

/**
 * 메일 링크의 토큰 확인 (로그인 없이, A72). 링크는 한 번만 쓸 수 있어서
 * 같은 토큰을 두 번 보내지 않도록 조회로 묶어 한 번만 부른다(다시 시도·다시 조회 없음).
 */
export function verifyLinkQuery(token: string) {
  return queryOptions({
    queryKey: ["profile", "verify-link", token] as const,
    queryFn: async () => {
      await unwrap(api.POST("/api/v1/auth/password-change/verify", { body: { token } }));
      return true as const;
    },
    retry: false,
    staleTime: Infinity,
    gcTime: Infinity,
  });
}
