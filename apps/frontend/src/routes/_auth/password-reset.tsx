import { createFileRoute } from "@tanstack/react-router";

import { PasswordResetPage } from "@/features/auth/components/password-reset-page";

export const Route = createFileRoute("/_auth/password-reset")({
  component: PasswordResetPage,
});
