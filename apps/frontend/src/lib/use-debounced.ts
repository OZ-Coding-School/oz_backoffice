import { useEffect, useState } from "react";

/** 입력이 멈추고 `ms` 뒤의 값 (검색창) */
export function useDebounced(value: string, ms = 300): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}
