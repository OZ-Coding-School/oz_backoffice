import { useCallback, useState } from "react";

/**
 * 가입 진행 상태 (decisions F24). 이 탭의 sessionStorage에 두어 새로고침해도 같은 단계로 돌아온다.
 * 비밀번호·인증코드는 저장하지 않는다. 가입 토큰은 가입에만 쓰는 30분짜리 토큰이다.
 */
export type SignupType = "STUDENT" | "MENTOR";
export type SignupStep = "type" | "email" | "email-code" | "phone" | "phone-code" | "info";

export interface SignupState {
  step: SignupStep;
  type: SignupType;
  email: string;
  /** 이메일 코드를 보낸 시각 (epoch ms) — 남은 시간·재발송 대기 계산 */
  emailSentAt: number | null;
  signupToken: string | null;
  /** 가입 토큰 만료 시각 (epoch ms) */
  tokenExpiresAt: number | null;
  phone: string;
  phoneSentAt: number | null;
}

const KEY = "oz-signup";
export const INITIAL: SignupState = {
  step: "type",
  type: "STUDENT",
  email: "",
  emailSentAt: null,
  signupToken: null,
  tokenExpiresAt: null,
  phone: "",
  phoneSentAt: null,
};

function load(): SignupState {
  try {
    const raw = window.sessionStorage.getItem(KEY);
    return raw ? { ...INITIAL, ...(JSON.parse(raw) as Partial<SignupState>) } : INITIAL;
  } catch {
    return INITIAL;
  }
}

function save(state: SignupState | null): void {
  try {
    if (state === null || state.step === "type") window.sessionStorage.removeItem(KEY);
    else window.sessionStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    // 저장소를 쓸 수 없으면 새로고침 때 처음부터 다시 한다
  }
}

export function useSignupState() {
  const [state, setState] = useState<SignupState>(load);
  const update = useCallback((patch: Partial<SignupState>) => {
    setState((prev) => {
      const next = { ...prev, ...patch };
      save(next);
      return next;
    });
  }, []);
  const reset = useCallback(() => {
    save(null);
    setState(INITIAL);
  }, []);
  return { state, update, reset };
}

/** 가입 토큰이 아직 쓸 수 있는가 (만료 1분 전부터는 만료로 본다). */
export function tokenAlive(state: SignupState, now: number = Date.now()): boolean {
  return state.signupToken !== null && state.tokenExpiresAt !== null && state.tokenExpiresAt - now > 60_000;
}
