import { Moon, Sun } from "lucide-react";

import { setThemePreference, useTheme } from "@/lib/theme";

import { Button } from "./ui/button";

/** 상단 막대 테마 버튼: 누를 때마다 라이트↔다크 (F27). 처음에는 시스템 설정을 따른다 (F18). */
export function ThemeToggle() {
  const { resolved } = useTheme();
  const dark = resolved === "dark";
  return (
    <Button
      variant="ghost"
      size="sm"
      className="px-2"
      aria-label={dark ? "라이트 모드로 바꾸기" : "다크 모드로 바꾸기"}
      onClick={() => setThemePreference(dark ? "light" : "dark")}
    >
      {dark ? <Moon /> : <Sun />}
    </Button>
  );
}
