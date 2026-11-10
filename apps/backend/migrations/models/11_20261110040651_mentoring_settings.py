from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "mentoring_holidays" (
    "id" UUID NOT NULL PRIMARY KEY,
    "holiday_date" DATE NOT NULL UNIQUE,
    "name" VARCHAR(50) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL
);
        CREATE TABLE IF NOT EXISTS "cohort_mentoring_block_times" (
    "id" UUID NOT NULL PRIMARY KEY,
    "period_start" DATE NOT NULL,
    "period_end" DATE NOT NULL,
    "start_time" TIMETZ NOT NULL,
    "end_time" TIMETZ NOT NULL,
    "reason" VARCHAR(200),
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "cohort_id" UUID NOT NULL REFERENCES "cohorts" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_cohort_ment_cohort__307f8b" ON "cohort_mentoring_block_times" ("cohort_id", "period_start");
        CREATE TABLE IF NOT EXISTS "cohort_mentoring_settings" (
    "id" UUID NOT NULL PRIMARY KEY,
    "allow_team_mentoring" BOOL NOT NULL,
    "allow_1_on_1" BOOL NOT NULL,
    "default_1on1_minutes" INT NOT NULL,
    "default_team_minutes" INT NOT NULL,
    "min_lead_hours" SMALLINT NOT NULL,
    "allowed_duration" SMALLINT NOT NULL,
    "max_pending_requests" SMALLINT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "cohort_id" UUID NOT NULL UNIQUE REFERENCES "cohorts" ("id") ON DELETE RESTRICT
);
-- raw SQL: 금지 시각은 한국 시각의 "시:분"이라 시간대 없는 TIME으로 둔다 (Tortoise use_tz는 TIMETZ를 만든다)
ALTER TABLE "cohort_mentoring_block_times"
    ALTER COLUMN "start_time" TYPE TIME USING "start_time"::TIME,
    ALTER COLUMN "end_time" TYPE TIME USING "end_time"::TIME,
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_block_period" CHECK ("period_start" <= "period_end"),
    ADD CONSTRAINT "check_block_time" CHECK ("start_time" < "end_time"),
    -- 같은 기수에서 기간과 시간대가 모두 겹치면 안 된다 (A34)
    ADD CONSTRAINT "excl_block_times_overlap" EXCLUDE USING gist (
        "cohort_id" WITH =,
        daterange("period_start", "period_end", '[]') WITH &&,
        tsrange(DATE '2000-01-01' + "start_time", DATE '2000-01-01' + "end_time") WITH &&
    );
ALTER TABLE "cohort_mentoring_settings"
    ALTER COLUMN "allow_team_mentoring" SET DEFAULT false,
    ALTER COLUMN "allow_1_on_1" SET DEFAULT false,
    ALTER COLUMN "default_1on1_minutes" SET DEFAULT 0,
    ALTER COLUMN "default_team_minutes" SET DEFAULT 0,
    ALTER COLUMN "min_lead_hours" SET DEFAULT 24,
    ALTER COLUMN "allowed_duration" SET DEFAULT 30,
    ALTER COLUMN "max_pending_requests" SET DEFAULT 1,
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_settings_default_minutes"
        CHECK ("default_1on1_minutes" >= 0 AND "default_team_minutes" >= 0),
    ADD CONSTRAINT "check_settings_rules"
        CHECK ("min_lead_hours" >= 0 AND "max_pending_requests" > 0 AND "allowed_duration" > 0),
    ADD CONSTRAINT "check_settings_allowed_duration" CHECK ("allowed_duration" IN (30, 60)),
    ADD CONSTRAINT "check_settings_min_lead_hours" CHECK ("min_lead_hours" IN (6, 12, 24)),
    ADD CONSTRAINT "check_settings_max_pending" CHECK ("max_pending_requests" BETWEEN 1 AND 3),
    ADD CONSTRAINT "check_settings_default_hours"
        CHECK ("default_1on1_minutes" % 60 = 0 AND "default_team_minutes" % 60 = 0),
    ADD CONSTRAINT "check_settings_some_mode" CHECK ("allow_team_mentoring" OR "allow_1_on_1");
ALTER TABLE "mentoring_holidays"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now();"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "mentoring_holidays";
        DROP TABLE IF EXISTS "cohort_mentoring_block_times";
        DROP TABLE IF EXISTS "cohort_mentoring_settings";"""


MODELS_STATE = (
    "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"
    "=="
)
