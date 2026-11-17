import { act, renderHook } from "@testing-library/react";

import {
  applyTheme,
  readPreference,
  resolveTheme,
  setThemePreference,
  THEME_STORAGE_KEY,
  useTheme,
  watchSystemTheme,
} from "./theme";

let systemDark = false;
let mediaListeners: (() => void)[] = [];

beforeEach(() => {
  systemDark = false;
  mediaListeners = [];
  window.localStorage.clear();
  document.documentElement.className = "";
  document.documentElement.style.colorScheme = "";
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({
      get matches() {
        return systemDark;
      },
      addEventListener: (_: string, listener: () => void) => mediaListeners.push(listener),
      removeEventListener: (_: string, listener: () => void) => {
        mediaListeners = mediaListeners.filter((l) => l !== listener);
      },
    })),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("테마", () => {
  it("저장된 값이 없거나 잘못되면 시스템을 따른다", () => {
    expect(readPreference()).toBe("system");
    window.localStorage.setItem(THEME_STORAGE_KEY, "blue");
    expect(readPreference()).toBe("system");
  });

  it("시스템이면 OS 설정으로, 아니면 고른 값으로 정한다", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("고른 테마를 기억하고 루트에 적용한다", () => {
    setThemePreference("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(document.documentElement).toHaveClass("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");

    setThemePreference("system");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
    expect(document.documentElement).not.toHaveClass("dark");
  });

  it("저장소를 쓸 수 없어도 이번 화면에는 적용한다", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    setThemePreference("dark");
    expect(document.documentElement).toHaveClass("dark");
    vi.restoreAllMocks();
  });

  it("시스템을 고른 경우에만 OS 설정 변경을 따라간다", () => {
    const stop = watchSystemTheme();
    applyTheme();
    systemDark = true;
    mediaListeners.forEach((listener) => listener());
    expect(document.documentElement).toHaveClass("dark");

    setThemePreference("light");
    systemDark = false;
    mediaListeners.forEach((listener) => listener());
    systemDark = true;
    mediaListeners.forEach((listener) => listener());
    expect(document.documentElement).not.toHaveClass("dark");
    stop();
    expect(mediaListeners).toHaveLength(0);
  });

  it("useTheme은 바뀐 값을 다시 렌더링한다", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current).toEqual({ preference: "system", resolved: "light" });
    act(() => setThemePreference("dark"));
    expect(result.current).toEqual({ preference: "dark", resolved: "dark" });
  });
});
