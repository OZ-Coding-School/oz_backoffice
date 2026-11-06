from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "permissions" (
    "id" UUID NOT NULL PRIMARY KEY,
    "code" VARCHAR(100) NOT NULL UNIQUE,
    "description" TEXT
);
        CREATE TABLE IF NOT EXISTS "roles" (
    "id" UUID NOT NULL PRIMARY KEY,
    "code" VARCHAR(50) NOT NULL UNIQUE,
    "name" VARCHAR(50) NOT NULL,
    "description" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL
);
        CREATE TABLE IF NOT EXISTS "user_roles" (
    "id" UUID NOT NULL PRIMARY KEY,
    "scope_type" VARCHAR(20) NOT NULL,
    "scope_id" UUID,
    "expires_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL,
    "role_id" UUID NOT NULL REFERENCES "roles" ("id") ON DELETE RESTRICT,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_user_roles_scope_t_eaa2fd" ON "user_roles" ("scope_type", "scope_id");
COMMENT ON COLUMN "user_roles"."scope_type" IS 'GLOBAL: GLOBAL\nBOOTCAMP: BOOTCAMP\nCOHORT: COHORT';
        CREATE TABLE "role_permissions" (
    "permission_id" UUID NOT NULL REFERENCES "permissions" ("id") ON DELETE CASCADE,
    "role_id" UUID NOT NULL REFERENCES "roles" ("id") ON DELETE CASCADE
);
-- ---------------------------------------------------------------
-- raw SQL: 복합 PK, NULLS NOT DISTINCT 유일 제약, check·enum 값·기본값
-- ---------------------------------------------------------------
ALTER TABLE "role_permissions"
    ADD CONSTRAINT "pk_role_permissions" PRIMARY KEY ("role_id", "permission_id");
ALTER TABLE "roles"
    ALTER COLUMN "created_at" SET DEFAULT now();
ALTER TABLE "user_roles"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_user_roles_scope_type" CHECK ("scope_type" IN ('GLOBAL', 'BOOTCAMP', 'COHORT')),
    ADD CONSTRAINT "check_user_role_scope" CHECK (("scope_type" = 'GLOBAL') = ("scope_id" IS NULL));
-- GLOBAL 역할(scope_id NULL)도 중복 부여를 막도록 NULLS NOT DISTINCT
CREATE UNIQUE INDEX "uid_user_roles_user_role_scope"
    ON "user_roles" ("user_id", "role_id", "scope_type", "scope_id") NULLS NOT DISTINCT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    # aerich 생성 순서는 FK 의존을 고려하지 않아 실패하므로, 참조하는 쪽부터 지우도록 바로잡았다
    return """
        DROP TABLE IF EXISTS "role_permissions";
        DROP TABLE IF EXISTS "user_roles";
        DROP TABLE IF EXISTS "permissions";
        DROP TABLE IF EXISTS "roles";"""


MODELS_STATE = (
    "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"
)
