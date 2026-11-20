/** 휴대폰 가운데 4자리를 가린다: 01012341234 → 010-****-1234 (F37) */
export function maskPhone(phone: string | null | undefined): string | null {
  const digits = (phone ?? "").replace(/\D/g, "");
  if (digits.length < 10) return phone ? phone : null;
  return `${digits.slice(0, 3)}-****-${digits.slice(-4)}`;
}

/** 이메일 아이디를 앞 2자만 남기고 가린다: student@example.com → st****@example.com */
export function maskEmail(email: string): string {
  const at = email.indexOf("@");
  if (at <= 0) return email;
  const id = email.slice(0, at);
  return `${id.slice(0, Math.min(2, id.length))}****${email.slice(at)}`;
}
