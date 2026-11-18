export interface BrandCopy {
  headline: string;
  features?: string[];
}

/** 수강생·멘토 화면 소개 문구 (F22). 운영진 화면은 FE-1c에서 기능 목록과 함께 쓴다. */
export const MEMBER_BRAND: BrandCopy = { headline: "수강부터 수료까지\n필요한 지원을 한곳에서" };

/** 운영진 화면 소개 문구와 기능 목록 (F22). */
export const STAFF_BRAND: BrandCopy = {
  headline: "오즈코딩스쿨 운영을\n한곳에서",
  features: ["학사 · 수강생 명단 관리", "멘토링 · 출결 · 행정 업무", "회원 가입 승인 · 권한 관리"],
};
