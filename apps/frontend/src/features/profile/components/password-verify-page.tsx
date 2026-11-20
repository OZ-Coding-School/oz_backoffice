import { useQuery } from "@tanstack/react-query";
import { CircleCheck, TriangleAlert } from "lucide-react";

import { Spinner } from "@/components/ui/spinner";

import { verifyLinkQuery } from "../api";

/** 메일 링크 인증 (Figma `Screen / 비밀번호 변경 인증`, A72·F37). 열어 둔 내 정보 창이 5초 안에 알아챈다 */
export function PasswordVerifyPage({ token }: { token: string }) {
  const verify = useQuery({ ...verifyLinkQuery(token), enabled: token.length > 0 });
  const ok = verify.isSuccess;
  const failed = verify.isError || token.length === 0;
  if (!ok && !failed) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }
  const Icon = ok ? CircleCheck : TriangleAlert;
  return (
    <div className="flex flex-col items-center gap-3 py-6 text-center">
      <span
        aria-hidden
        className={`inline-flex size-12 items-center justify-center rounded-full ${ok ? "bg-success-subtle" : "bg-destructive-subtle"}`}
      >
        <Icon className={`size-6 ${ok ? "text-success-text" : "text-destructive-text"}`} />
      </span>
      <h1 className="text-h2 text-foreground">{ok ? "이메일 인증이 완료되었습니다." : "링크를 쓸 수 없어요"}</h1>
      <p className="text-body-sm whitespace-pre-line text-muted-foreground">
        {ok
          ? "열어 둔 내 정보 화면으로 돌아가\n새 비밀번호를 입력해 주세요. 이 창은 닫아도 돼요."
          : "링크가 만료됐거나 이미 사용됐어요.\n내 정보에서 인증 링크를 다시 보내 주세요."}
      </p>
    </div>
  );
}
