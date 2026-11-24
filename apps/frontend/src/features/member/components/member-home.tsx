import type { Me } from "@/features/auth/api";
import { MentorHome } from "@/features/home/components/mentor-home";
import { StudentHome } from "@/features/home/components/student-home";

/** 회원 홈 (F27). 수강생은 할 일 요약(FE-8, F42), 멘토는 할 일 요약(FE-13, F57) */
export function MemberHome({ me }: { me: Me }) {
  return me.account_type === "STUDENT" ? <StudentHome me={me} /> : <MentorHome me={me} />;
}
