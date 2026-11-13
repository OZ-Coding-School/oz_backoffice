from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "mentoring_settlements" (
    "id" UUID NOT NULL PRIMARY KEY,
    "settlement_month" DATE NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "session_count" INT NOT NULL,
    "total_minutes" INT NOT NULL,
    "total_amount" INT NOT NULL,
    "closed_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "cohort_id" UUID NOT NULL REFERENCES "cohorts" ("id") ON DELETE RESTRICT,
    "mentor_id" UUID NOT NULL REFERENCES "mentors" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_mentoring_s_mentor__1e7c72" UNIQUE ("mentor_id", "cohort_id", "settlement_month")
);
CREATE INDEX IF NOT EXISTS "idx_mentoring_s_cohort__3e1bc9" ON "mentoring_settlements" ("cohort_id", "settlement_month");
COMMENT ON COLUMN "mentoring_settlements"."status" IS 'DRAFT: DRAFT\nCLOSED: CLOSED';
        CREATE TABLE IF NOT EXISTS "mentoring_settlement_items" (
    "id" UUID NOT NULL PRIMARY KEY,
    "item_type" VARCHAR(20) NOT NULL,
    "settlement_policy" VARCHAR(30) NOT NULL,
    "billable_minutes" INT NOT NULL,
    "pay_unit" VARCHAR(20) NOT NULL,
    "pay_rate" INT NOT NULL,
    "amount" INT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "cohort_id" UUID NOT NULL REFERENCES "cohorts" ("id") ON DELETE RESTRICT,
    "settlement_id" UUID NOT NULL REFERENCES "mentoring_settlements" ("id") ON DELETE CASCADE,
    "session_id" UUID NOT NULL UNIQUE REFERENCES "mentoring_sessions" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_mentoring_s_settlem_7131c5" ON "mentoring_settlement_items" ("settlement_id");
COMMENT ON COLUMN "mentoring_settlement_items"."item_type" IS 'SESSION: SESSION\nNO_SHOW: NO_SHOW';
COMMENT ON COLUMN "mentoring_settlement_items"."settlement_policy" IS 'STUDENT_REQUEST: STUDENT_REQUEST\nACTUAL_DURATION: ACTUAL_DURATION';
COMMENT ON COLUMN "mentoring_settlement_items"."pay_unit" IS 'HOURLY: HOURLY\nPER_SESSION: PER_SESSION\nMONTHLY: MONTHLY\nLUMP_SUM: LUMP_SUM';
-- raw SQL: 정산 (M16·M30·A55)
ALTER TABLE "mentoring_settlements"
    ALTER COLUMN "status" SET DEFAULT 'DRAFT',
    ALTER COLUMN "session_count" SET DEFAULT 0,
    ALTER COLUMN "total_minutes" SET DEFAULT 0,
    ALTER COLUMN "total_amount" SET DEFAULT 0,
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_settlement_status" CHECK ("status" IN ('DRAFT', 'CLOSED')),
    ADD CONSTRAINT "check_settlement_closed" CHECK (("status" = 'CLOSED') = ("closed_at" IS NOT NULL)),
    ADD CONSTRAINT "check_settlement_month" CHECK (EXTRACT(DAY FROM "settlement_month") = 1),
    ADD CONSTRAINT "check_settlement_totals"
        CHECK ("session_count" >= 0 AND "total_minutes" >= 0 AND "total_amount" >= 0);
ALTER TABLE "mentoring_settlement_items"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_settlement_item_type" CHECK ("item_type" IN ('SESSION', 'NO_SHOW')),
    ADD CONSTRAINT "check_settlement_item_policy"
        CHECK ("settlement_policy" IN ('STUDENT_REQUEST', 'ACTUAL_DURATION')),
    -- 멘토링 정산은 시급·회당만 (M30)
    ADD CONSTRAINT "check_settlement_item_pay_unit" CHECK ("pay_unit" IN ('HOURLY', 'PER_SESSION')),
    ADD CONSTRAINT "check_settlement_item_values"
        CHECK ("billable_minutes" >= 0 AND "pay_rate" >= 0 AND "amount" >= 0);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "mentoring_settlement_items";
        DROP TABLE IF EXISTS "mentoring_settlements";"""


MODELS_STATE = (
    "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"
    "z/8DZfWD5g=="
)
