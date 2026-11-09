from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "contract_files" (
    "id" UUID NOT NULL PRIMARY KEY,
    "file_name" VARCHAR(100) NOT NULL,
    "file_ext" VARCHAR(10) NOT NULL,
    "file_size" BIGINT NOT NULL,
    "storage_key" VARCHAR(1024) NOT NULL UNIQUE,
    "created_at" TIMESTAMPTZ NOT NULL,
    "deleted_at" TIMESTAMPTZ
);
        CREATE TABLE IF NOT EXISTS "instructors" (
    "id" UUID NOT NULL PRIMARY KEY,
    "nickname" VARCHAR(30),
    "display_name_preference" VARCHAR(10) NOT NULL,
    "headline" VARCHAR(100),
    "introduction" TEXT,
    "expertise" VARCHAR(200),
    "profile_image_key" VARCHAR(1024),
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "user_id" UUID NOT NULL UNIQUE REFERENCES "users" ("id") ON DELETE RESTRICT
);
COMMENT ON COLUMN "instructors"."display_name_preference" IS 'NAME: NAME\nNICKNAME: NICKNAME';
        CREATE TABLE IF NOT EXISTS "mentors" (
    "id" UUID NOT NULL PRIMARY KEY,
    "nickname" VARCHAR(30),
    "display_name_preference" VARCHAR(10) NOT NULL,
    "headline" VARCHAR(100),
    "introduction" TEXT,
    "expertise" VARCHAR(200),
    "profile_image_key" VARCHAR(1024),
    "is_active" BOOL NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "user_id" UUID NOT NULL UNIQUE REFERENCES "users" ("id") ON DELETE RESTRICT
);
COMMENT ON COLUMN "mentors"."display_name_preference" IS 'NAME: NAME\nNICKNAME: NICKNAME';
        CREATE TABLE IF NOT EXISTS "educator_contracts" (
    "id" UUID NOT NULL PRIMARY KEY,
    "educator_type" VARCHAR(20) NOT NULL,
    "contractor_name" VARCHAR(50) NOT NULL,
    "contractor_email" VARCHAR(255),
    "contractor_phone" VARCHAR(11) NOT NULL,
    "title" VARCHAR(100) NOT NULL,
    "start_date" DATE NOT NULL,
    "end_date" DATE NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "instructor_id" UUID REFERENCES "instructors" ("id") ON DELETE RESTRICT,
    "manager_employee_id" UUID NOT NULL REFERENCES "employees" ("id") ON DELETE RESTRICT,
    "mentor_id" UUID REFERENCES "mentors" ("id") ON DELETE RESTRICT,
    "contract_file_id" UUID UNIQUE REFERENCES "contract_files" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_educator_co_contrac_540495" ON "educator_contracts" ("contractor_name", "contractor_phone");
CREATE INDEX IF NOT EXISTS "idx_educator_co_mentor__66c0c1" ON "educator_contracts" ("mentor_id");
CREATE INDEX IF NOT EXISTS "idx_educator_co_instruc_b8e64a" ON "educator_contracts" ("instructor_id");
COMMENT ON COLUMN "educator_contracts"."educator_type" IS 'MENTOR: MENTOR\nINSTRUCTOR: INSTRUCTOR';
COMMENT ON COLUMN "educator_contracts"."status" IS 'DRAFT: DRAFT\nACTIVE: ACTIVE\nENDED: ENDED\nTERMINATED: TERMINATED';
-- raw SQL: DB 기본값과 DBML check 제약 (aerich가 만들지 않는다)
ALTER TABLE "contract_files"
    ALTER COLUMN "created_at" SET DEFAULT now();
ALTER TABLE "mentors"
    ALTER COLUMN "display_name_preference" SET DEFAULT 'NAME',
    ALTER COLUMN "is_active" SET DEFAULT true,
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_mentors_display_name_preference"
        CHECK ("display_name_preference" IN ('NAME', 'NICKNAME')),
    ADD CONSTRAINT "check_mentor_display_nickname"
        CHECK ("display_name_preference" = 'NAME' OR "nickname" IS NOT NULL);
ALTER TABLE "instructors"
    ALTER COLUMN "display_name_preference" SET DEFAULT 'NAME',
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_instructors_display_name_preference"
        CHECK ("display_name_preference" IN ('NAME', 'NICKNAME')),
    ADD CONSTRAINT "check_instructor_display_nickname"
        CHECK ("display_name_preference" = 'NAME' OR "nickname" IS NOT NULL);
ALTER TABLE "educator_contracts"
    ALTER COLUMN "status" SET DEFAULT 'DRAFT',
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_educator_contracts_educator_type"
        CHECK ("educator_type" IN ('MENTOR', 'INSTRUCTOR')),
    ADD CONSTRAINT "check_educator_contracts_status"
        CHECK ("status" IN ('DRAFT', 'ACTIVE', 'ENDED', 'TERMINATED')),
    ADD CONSTRAINT "check_contract_period" CHECK ("start_date" <= "end_date"),
    ADD CONSTRAINT "check_contract_email_lowercase"
        CHECK ("contractor_email" IS NULL OR "contractor_email" = lower("contractor_email")),
    ADD CONSTRAINT "check_contract_educator_type"
        CHECK (("educator_type" = 'MENTOR' OR "mentor_id" IS NULL)
            AND ("educator_type" = 'INSTRUCTOR' OR "instructor_id" IS NULL)),
    ADD CONSTRAINT "check_contract_file_required"
        CHECK ("status" = 'DRAFT' OR "contract_file_id" IS NOT NULL);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "educator_contracts";
        DROP TABLE IF EXISTS "instructors";
        DROP TABLE IF EXISTS "mentors";
        DROP TABLE IF EXISTS "contract_files";"""


MODELS_STATE = (
    "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"
    "vFL/ZPb7/wHFbjdd"
)
