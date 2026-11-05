from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "employee_registrations" (
    "id" UUID NOT NULL PRIMARY KEY,
    "employment_type" VARCHAR(20) NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "reviewed_at" TIMESTAMPTZ,
    "reject_reason" VARCHAR(300),
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "department_id" UUID NOT NULL REFERENCES "departments" ("id") ON DELETE RESTRICT,
    "position_id" UUID NOT NULL REFERENCES "employee_positions" ("id") ON DELETE RESTRICT,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_employee_re_user_id_baa3b5" ON "employee_registrations" ("user_id", "created_at");
CREATE INDEX IF NOT EXISTS "idx_employee_re_status_149171" ON "employee_registrations" ("status", "created_at");
COMMENT ON COLUMN "employee_registrations"."employment_type" IS 'REGULAR: REGULAR\nCONTRACT: CONTRACT\nINTERN: INTERN\nPART_TIME_JOB: PART_TIME_JOB\nFREELANCER: FREELANCER\nDAILY: DAILY';
COMMENT ON COLUMN "employee_registrations"."status" IS 'PENDING: PENDING\nAPPROVED: APPROVED\nREJECTED: REJECTED';
        CREATE TABLE IF NOT EXISTS "employee_registration_assignments" (
    "id" UUID NOT NULL PRIMARY KEY,
    "role" VARCHAR(20) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "bootcamp_id" UUID REFERENCES "bootcamps" ("id") ON DELETE RESTRICT,
    "cohort_id" UUID REFERENCES "cohorts" ("id") ON DELETE RESTRICT,
    "registration_id" UUID NOT NULL REFERENCES "employee_registrations" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "employee_registration_assignments"."role" IS 'MANAGER: MANAGER\nASSISTANT: ASSISTANT';
-- ---------------------------------------------------------------
-- raw SQL: 부분 유니크, NULLS NOT DISTINCT 유일 제약, check·enum 값·기본값
-- ---------------------------------------------------------------
ALTER TABLE "employee_registrations"
    ALTER COLUMN "status" SET DEFAULT 'PENDING',
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_employee_registrations_status"
        CHECK ("status" IN ('PENDING', 'APPROVED', 'REJECTED')),
    ADD CONSTRAINT "check_employee_registrations_employment_type"
        CHECK ("employment_type" IN ('REGULAR', 'CONTRACT', 'INTERN', 'PART_TIME_JOB',
               'FREELANCER', 'DAILY')),
    ADD CONSTRAINT "check_employee_registrations_reviewed"
        CHECK (("status" = 'PENDING') = ("reviewed_at" IS NULL)),
    ADD CONSTRAINT "check_employee_registrations_reject_reason"
        CHECK ("status" = 'REJECTED' OR "reject_reason" IS NULL);
-- 회원당 대기 중 신청은 하나
CREATE UNIQUE INDEX "uid_employee_registrations_pending_user"
    ON "employee_registrations" ("user_id") WHERE "status" = 'PENDING';
ALTER TABLE "employee_registration_assignments"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_employee_registration_assignments_role"
        CHECK ("role" IN ('MANAGER', 'ASSISTANT')),
    ADD CONSTRAINT "check_employee_registration_assignments_target"
        CHECK (num_nonnulls("bootcamp_id", "cohort_id") = 1);
-- 같은 신청 안에서 (역할, 과정, 기수) 중복 방지. 과정·기수 중 하나는 항상 NULL이라 NULLS NOT DISTINCT
CREATE UNIQUE INDEX "uid_employee_registration_assignments_target"
    ON "employee_registration_assignments" ("registration_id", "role", "bootcamp_id", "cohort_id")
    NULLS NOT DISTINCT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    # aerich 생성 순서는 FK 의존을 고려하지 않아 실패하므로, 참조하는 쪽부터 지우도록 바로잡았다
    return """
        DROP TABLE IF EXISTS "employee_registration_assignments";
        DROP TABLE IF EXISTS "employee_registrations";"""


MODELS_STATE = (
    "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"
    "mIS4cMjF7Nf/Acq1Krk="
)
