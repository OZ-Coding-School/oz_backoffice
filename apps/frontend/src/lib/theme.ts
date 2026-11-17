import { useSyncExternalStore } from "react";

/** 사용자가 고른 테마. system은 OS 설정을 따른다 (decisions F18). */
export type ThemePreference = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

/** index.html의 첫 화면 스크립트와 같은 키를 쓴다. */
export const THEME_STORAGE_KEY = "oz-theme";

const DARK_QUERY = "(prefers-color-scheme: dark)";
const listeners = new Set<() => void>();

function isPreference(value: unknown): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark";
}

export function readPreference(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isPreference(stored) ? stored : "system";
  } catch {
    // 저장소를 쓸 수 없는 환경(사생활 보호 모드 등)에서는 시스템 설정을 따른다
    return "system";
  }
}

export function resolveTheme(preference: ThemePreference, systemDark: boolean): ResolvedTheme {
  if (preference === "system") return systemDark ? "dark" : "light";
  return preference;
}

function systemPrefersDark(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia(DARK_QUERY).matches;
}

/** 문서 루트에 테마를 적용한다. 다크는 `.dark` 클래스, 브라우저 기본 UI는 color-scheme으로 맞춘다. */
export function applyTheme(preference: ThemePreference = readPreference()): ResolvedTheme {
  const resolved = resolveTheme(preference, systemPrefersDark());
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  root.style.colorScheme = resolved;
  return resolved;
}

export function setThemePreference(preference: ThemePreference): void {
  try {
    if (preference === "system") window.localStorage.removeItem(THEME_STORAGE_KEY);
    else window.localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // 기억하지 못해도 이번 화면에는 적용한다
  }
  applyTheme(preference);
  listeners.forEach((listener) => listener());
}

/** 시스템 설정이 바뀌면 system을 고른 경우에만 다시 적용한다. 앱 시작 시 한 번 부른다. */
export function watchSystemTheme(): () => void {
  if (typeof window.matchMedia !== "function") return () => {};
  const media = window.matchMedia(DARK_QUERY);
  const onChange = () => {
    if (readPreference() === "system") {
      applyTheme("system");
      listeners.forEach((listener) => listener());
    }
  };
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** 현재 고른 테마와 실제 적용된 테마. */
export function useTheme(): { preference: ThemePreference; resolved: ResolvedTheme } {
  const preference = useSyncExternalStore(subscribe, readPreference, () => "system" as const);
  const resolved = useSyncExternalStore(
    subscribe,
    () => resolveTheme(readPreference(), systemPrefersDark()),
    () => "light" as const,
  );
  return { preference, resolved };
}
