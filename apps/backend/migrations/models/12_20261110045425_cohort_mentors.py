from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "cohort_mentors" (
    "id" UUID NOT NULL PRIMARY KEY,
    "period_type" VARCHAR(30) NOT NULL,
    "start_date" DATE NOT NULL,
    "end_date" DATE,
    "cost_settlement_policy" VARCHAR(30) NOT NULL,
    "pay_unit" VARCHAR(20) NOT NULL,
    "pay_rate" INT NOT NULL,
    "no_show_pay_amount" INT NOT NULL,
    "is_active" BOOL NOT NULL,
    "deactivated_at" TIMESTAMPTZ,
    "deactivation_reason" VARCHAR(30),
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "cohort_id" UUID NOT NULL REFERENCES "cohorts" ("id") ON DELETE RESTRICT,
    "mentor_id" UUID NOT NULL REFERENCES "mentors" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_cohort_ment_cohort__f3dc2e" ON "cohort_mentors" ("cohort_id", "is_active");
CREATE INDEX IF NOT EXISTS "idx_cohort_ment_is_acti_9b14d8" ON "cohort_mentors" ("is_active", "end_date");
CREATE INDEX IF NOT EXISTS "idx_cohort_ment_mentor__a4915a" ON "cohort_mentors" ("mentor_id", "is_active");
COMMENT ON COLUMN "cohort_mentors"."period_type" IS 'PROJECT_MENTORING: PROJECT_MENTORING\nREGULAR_MENTORING: REGULAR_MENTORING';
COMMENT ON COLUMN "cohort_mentors"."cost_settlement_policy" IS 'STUDENT_REQUEST: STUDENT_REQUEST\nACTUAL_DURATION: ACTUAL_DURATION';
COMMENT ON COLUMN "cohort_mentors"."pay_unit" IS 'HOURLY: HOURLY\nPER_SESSION: PER_SESSION\nMONTHLY: MONTHLY\nLUMP_SUM: LUMP_SUM';
COMMENT ON COLUMN "cohort_mentors"."deactivation_reason" IS 'EXPIRED: EXPIRED\nMANUAL: MANUAL\nMENTOR_DEACTIVATED: MENTOR_DEACTIVATED';
-- raw SQL: 기본값, enum·DBML check, 활성 배정은 (멘토, 기수, 유형)당 하나 (A35)
ALTER TABLE "cohort_mentors"
    ALTER COLUMN "no_show_pay_amount" SET DEFAULT 0,
    ALTER COLUMN "is_active" SET DEFAULT true,
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_cohort_mentors_period_type"
        CHECK ("period_type" IN ('PROJECT_MENTORING', 'REGULAR_MENTORING')),
    ADD CONSTRAINT "check_cohort_mentors_settlement_policy"
        CHECK ("cost_settlement_policy" IN ('STUDENT_REQUEST', 'ACTUAL_DURATION')),
    ADD CONSTRAINT "check_cohort_mentor_pay_unit" CHECK ("pay_unit" IN ('HOURLY', 'PER_SESSION')),
    ADD CONSTRAINT "check_cohort_mentors_deactivation_reason"
        CHECK ("deactivation_reason" IS NULL
            OR "deactivation_reason" IN ('EXPIRED', 'MANUAL', 'MENTOR_DEACTIVATED')),
    ADD CONSTRAINT "check_cohort_mentor_period"
        CHECK ("end_date" IS NULL OR "start_date" <= "end_date"),
    ADD CONSTRAINT "check_cohort_mentor_pay_rate"
        CHECK ("pay_rate" >= 0 AND "no_show_pay_amount" >= 0),
    ADD CONSTRAINT "check_cohort_mentor_deactivation"
        CHECK ("is_active" = ("deactivated_at" IS NULL)
            AND "is_active" = ("deactivation_reason" IS NULL));
CREATE UNIQUE INDEX "uid_cohort_mentors_active"
    ON "cohort_mentors" ("mentor_id", "cohort_id", "period_type") WHERE "is_active";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "uid_cohort_mentors_active";
        DROP TABLE IF EXISTS "cohort_mentors";"""


MODELS_STATE = (
    "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"
    "OciNYQ3tU/gxb0pt//X/GzwBGA=="
)
