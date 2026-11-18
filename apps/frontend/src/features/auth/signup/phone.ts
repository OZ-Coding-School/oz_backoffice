/** 휴대폰 번호: 화면에는 010-1234-5678, 보낼 때는 숫자만 (decisions F24, 백엔드 `^01[0-9]{8,9}$`). */
export function phoneDigits(value: string): string {
  return value.replace(/\D/g, "").slice(0, 11);
}

export function formatPhone(value: string): string {
  const d = phoneDigits(value);
  if (d.length < 4) return d;
  if (d.length < 8) return `${d.slice(0, 3)}-${d.slice(3)}`;
  const middle = d.length === 11 ? 4 : 3;
  return `${d.slice(0, 3)}-${d.slice(3, 3 + middle)}-${d.slice(3 + middle)}`;
}

export function isValidPhone(value: string): boolean {
  return /^01\d{8,9}$/.test(phoneDigits(value));
}
