from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "departments" (
    "id" UUID NOT NULL PRIMARY KEY,
    "parent_id" UUID,
    "name" VARCHAR(20) NOT NULL,
    "description" VARCHAR(500) NOT NULL,
    "rules" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL
);
        CREATE TABLE IF NOT EXISTS "employee_positions" (
    "id" UUID NOT NULL PRIMARY KEY,
    "name" VARCHAR(20) NOT NULL UNIQUE,
    "priority" SMALLINT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL
);
        CREATE TABLE IF NOT EXISTS "employees" (
    "id" UUID NOT NULL PRIMARY KEY,
    "employment_type" VARCHAR(20) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "department_id" UUID NOT NULL REFERENCES "departments" ("id") ON DELETE RESTRICT,
    "position_id" UUID NOT NULL REFERENCES "employee_positions" ("id") ON DELETE RESTRICT,
    "user_id" UUID NOT NULL UNIQUE REFERENCES "users" ("id") ON DELETE RESTRICT
);
COMMENT ON COLUMN "employees"."employment_type" IS 'REGULAR: REGULAR\nCONTRACT: CONTRACT\nINTERN: INTERN\nPART_TIME_JOB: PART_TIME_JOB\nFREELANCER: FREELANCER\nDAILY: DAILY';
        CREATE TABLE IF NOT EXISTS "bootcamp_staffs" (
    "id" UUID NOT NULL PRIMARY KEY,
    "role" VARCHAR(20) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "bootcamp_id" UUID NOT NULL REFERENCES "bootcamps" ("id") ON DELETE RESTRICT,
    "employee_id" UUID NOT NULL REFERENCES "employees" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_bootcamp_st_employe_d54add" UNIQUE ("employee_id", "bootcamp_id", "role")
);
CREATE INDEX IF NOT EXISTS "idx_bootcamp_st_bootcam_3b7361" ON "bootcamp_staffs" ("bootcamp_id");
COMMENT ON COLUMN "bootcamp_staffs"."role" IS 'MANAGER: MANAGER\nASSISTANT: ASSISTANT';
        CREATE TABLE IF NOT EXISTS "cohort_staffs" (
    "id" UUID NOT NULL PRIMARY KEY,
    "role" VARCHAR(20) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "cohort_id" UUID NOT NULL REFERENCES "cohorts" ("id") ON DELETE RESTRICT,
    "employee_id" UUID NOT NULL REFERENCES "employees" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_cohort_staf_employe_37071c" UNIQUE ("employee_id", "cohort_id", "role")
);
CREATE INDEX IF NOT EXISTS "idx_cohort_staf_cohort__2fec6f" ON "cohort_staffs" ("cohort_id");
COMMENT ON COLUMN "cohort_staffs"."role" IS 'MANAGER: MANAGER\nASSISTANT: ASSISTANT';
-- ---------------------------------------------------------------
-- raw SQL: 자기 참조 FK, NULLS NOT DISTINCT 유일 제약, check·enum 값·기본값
-- ---------------------------------------------------------------
ALTER TABLE "departments"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "fk_departments_parent"
        FOREIGN KEY ("parent_id") REFERENCES "departments" ("id") ON DELETE RESTRICT,
    ADD CONSTRAINT "check_departments_parent_not_self" CHECK ("parent_id" IS NULL OR "parent_id" <> "id");
-- 최상위 부서(parent_id NULL)끼리도 이름이 겹치지 않도록 NULLS NOT DISTINCT (PostgreSQL 15+)
CREATE UNIQUE INDEX "uid_departments_parent_name"
    ON "departments" ("parent_id", "name") NULLS NOT DISTINCT;
ALTER TABLE "employee_positions"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now();
ALTER TABLE "employees"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_employees_employment_type"
        CHECK ("employment_type" IN ('REGULAR', 'CONTRACT', 'INTERN', 'PART_TIME_JOB',
               'FREELANCER', 'DAILY'));
ALTER TABLE "bootcamp_staffs"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_bootcamp_staffs_role" CHECK ("role" IN ('MANAGER', 'ASSISTANT'));
ALTER TABLE "cohort_staffs"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_cohort_staffs_role" CHECK ("role" IN ('MANAGER', 'ASSISTANT'));"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    # aerich 생성 순서는 FK 의존을 고려하지 않아 실패하므로, 참조하는 쪽부터 지우도록 바로잡았다
    return """
        DROP TABLE IF EXISTS "cohort_staffs";
        DROP TABLE IF EXISTS "bootcamp_staffs";
        DROP TABLE IF EXISTS "employees";
        DROP TABLE IF EXISTS "employee_positions";
        DROP TABLE IF EXISTS "departments";"""


MODELS_STATE = (
    "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"
)
