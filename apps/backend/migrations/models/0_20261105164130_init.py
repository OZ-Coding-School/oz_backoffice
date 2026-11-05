from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" UUID NOT NULL PRIMARY KEY,
    "email" VARCHAR(255) NOT NULL UNIQUE,
    "hashed_password" VARCHAR(255),
    "name" VARCHAR(50) NOT NULL,
    "phone_number" VARCHAR(11) UNIQUE,
    "birth_date" DATE,
    "approval_status" VARCHAR(20) NOT NULL,
    "approved_at" TIMESTAMPTZ,
    "email_verified_at" TIMESTAMPTZ,
    "phone_verified_at" TIMESTAMPTZ,
    "is_active" BOOL NOT NULL,
    "last_login_at" TIMESTAMPTZ,
    "deleted_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL
);
COMMENT ON COLUMN "users"."approval_status" IS 'PENDING: PENDING\nAPPROVED: APPROVED\nREJECTED: REJECTED';
CREATE TABLE IF NOT EXISTS "oauth_accounts" (
    "id" UUID NOT NULL PRIMARY KEY,
    "provider" VARCHAR(20) NOT NULL,
    "oauth_provider_id" VARCHAR(255) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_oauth_accou_provide_9bf97f" UNIQUE ("provider", "oauth_provider_id"),
    CONSTRAINT "uid_oauth_accou_user_id_0a42ea" UNIQUE ("user_id", "provider")
);
COMMENT ON COLUMN "oauth_accounts"."provider" IS 'KAKAO: KAKAO\nGOOGLE: GOOGLE\nNAVER: NAVER';
CREATE TABLE IF NOT EXISTS "audit_logs" (
    "id" UUID NOT NULL PRIMARY KEY,
    "action" VARCHAR(100) NOT NULL,
    "target_type" VARCHAR(50) NOT NULL,
    "target_id" UUID,
    "before" JSONB,
    "after" JSONB,
    "ip" VARCHAR(45),
    "created_at" TIMESTAMPTZ NOT NULL,
    "actor_user_id" UUID REFERENCES "users" ("id") ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS "idx_audit_logs_target__f7a138" ON "audit_logs" ("target_type", "target_id", "created_at");
CREATE INDEX IF NOT EXISTS "idx_audit_logs_actor_u_107ac8" ON "audit_logs" ("actor_user_id", "created_at");
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);
-- ---------------------------------------------------------------
-- raw SQL: DBML 제약·기본값 (Tortoise로 표현할 수 없는 부분)
-- ---------------------------------------------------------------
ALTER TABLE "users"
    ALTER COLUMN "approval_status" SET DEFAULT 'PENDING',
    ALTER COLUMN "is_active" SET DEFAULT false,
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_users_email_lowercase" CHECK ("email" = lower("email")),
    ADD CONSTRAINT "check_users_approved_at" CHECK (("approval_status" = 'APPROVED') = ("approved_at" IS NOT NULL)),
    ADD CONSTRAINT "check_users_approval_status" CHECK ("approval_status" IN ('PENDING', 'APPROVED', 'REJECTED')),
    ADD CONSTRAINT "check_users_phone_number" CHECK ("phone_number" IS NULL OR "phone_number" ~ '^01[0-9]{8,9}$');
ALTER TABLE "oauth_accounts"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_oauth_accounts_provider" CHECK ("provider" IN ('KAKAO', 'GOOGLE', 'NAVER'));
ALTER TABLE "audit_logs"
    ALTER COLUMN "created_at" SET DEFAULT now();"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
)
