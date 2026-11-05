from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "hrd_net_bootcamps" (
    "id" UUID NOT NULL PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "hrd_net_id" VARCHAR(100) UNIQUE,
    "train_type" VARCHAR(10),
    "ncs1_se" VARCHAR(10),
    "ncs2_se" VARCHAR(10),
    "ncs3_se" VARCHAR(10),
    "weekend_se" VARCHAR(10) NOT NULL,
    "day_night_se" VARCHAR(10) NOT NULL,
    "total_train_fee" INT,
    "train_fee_per_hour" INT,
    "total_train_hours" SMALLINT,
    "total_train_days" SMALLINT,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL
);
COMMENT ON COLUMN "hrd_net_bootcamps"."train_type" IS 'KDT: KDT\nKDC: KDC';
COMMENT ON COLUMN "hrd_net_bootcamps"."weekend_se" IS 'WEEKEND: WEEKEND\nWEEKDAY: WEEKDAY\nHYBRID: HYBRID';
COMMENT ON COLUMN "hrd_net_bootcamps"."day_night_se" IS 'DAY: DAY\nNIGHT: NIGHT\nHYBRID: HYBRID';
        CREATE TABLE IF NOT EXISTS "bootcamps" (
    "id" UUID NOT NULL PRIMARY KEY,
    "name" VARCHAR(50) NOT NULL UNIQUE,
    "code" VARCHAR(20) NOT NULL UNIQUE,
    "is_active" BOOL NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "hrd_net_bootcamp_id" UUID NOT NULL REFERENCES "hrd_net_bootcamps" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_bootcamps_hrd_net_fa1b37" ON "bootcamps" ("hrd_net_bootcamp_id");
        CREATE TABLE IF NOT EXISTS "hrd_net_bootcamp_cohorts" (
    "id" UUID NOT NULL PRIMARY KEY,
    "cohort_number" SMALLINT NOT NULL,
    "train_start_date" DATE,
    "train_end_date" DATE,
    "self_pay_amount" INT,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "hrd_net_bootcamp_id" UUID NOT NULL REFERENCES "hrd_net_bootcamps" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_hrd_net_boo_hrd_net_f14b83" UNIQUE ("hrd_net_bootcamp_id", "cohort_number")
);
        CREATE TABLE IF NOT EXISTS "cohorts" (
    "id" UUID NOT NULL PRIMARY KEY,
    "cohort_number" SMALLINT NOT NULL,
    "start_date" DATE NOT NULL,
    "end_date" DATE NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "discord_guild_id" VARCHAR(32) UNIQUE,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "bootcamp_id" UUID NOT NULL REFERENCES "bootcamps" ("id") ON DELETE RESTRICT,
    "hrd_net_cohort_id" UUID NOT NULL REFERENCES "hrd_net_bootcamp_cohorts" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_cohorts_bootcam_ccfd3e" UNIQUE ("bootcamp_id", "cohort_number")
);
CREATE INDEX IF NOT EXISTS "idx_cohorts_hrd_net_16b463" ON "cohorts" ("hrd_net_cohort_id");
COMMENT ON COLUMN "cohorts"."status" IS 'PLANNED: PLANNED\nONGOING: ONGOING\nENDED: ENDED\nINACTIVE: INACTIVE\nARCHIVED: ARCHIVED';
        CREATE TABLE IF NOT EXISTS "roster_sync_runs" (
    "id" UUID NOT NULL PRIMARY KEY,
    "trigger" VARCHAR(20) NOT NULL,
    "scope_type" VARCHAR(20) NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "started_at" TIMESTAMPTZ NOT NULL,
    "finished_at" TIMESTAMPTZ,
    "fetched_count" INT NOT NULL,
    "upserted_count" INT NOT NULL,
    "removed_count" INT NOT NULL,
    "unmapped_count" INT NOT NULL,
    "error_message" TEXT,
    "bootcamp_id" UUID REFERENCES "bootcamps" ("id") ON DELETE RESTRICT,
    "cohort_id" UUID REFERENCES "cohorts" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_roster_sync_started_ff8363" ON "roster_sync_runs" ("started_at");
CREATE INDEX IF NOT EXISTS "idx_roster_sync_cohort__bd6a85" ON "roster_sync_runs" ("cohort_id", "started_at");
COMMENT ON COLUMN "roster_sync_runs"."trigger" IS 'SCHEDULED: SCHEDULED\nMANUAL: MANUAL';
COMMENT ON COLUMN "roster_sync_runs"."scope_type" IS 'ALL: ALL\nBOOTCAMP: BOOTCAMP\nCOHORT: COHORT';
COMMENT ON COLUMN "roster_sync_runs"."status" IS 'RUNNING: RUNNING\nSUCCEEDED: SUCCEEDED\nFAILED: FAILED';
        CREATE TABLE IF NOT EXISTS "students" (
    "id" UUID NOT NULL PRIMARY KEY,
    "status" VARCHAR(20) NOT NULL,
    "hrd_net_status" VARCHAR(30) NOT NULL,
    "enrolled_at" DATE NOT NULL,
    "ended_at" DATE,
    "end_reason" VARCHAR(200),
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "cohort_id" UUID NOT NULL REFERENCES "cohorts" ("id") ON DELETE RESTRICT,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_students_user_id_e25e30" UNIQUE ("user_id", "cohort_id")
);
CREATE INDEX IF NOT EXISTS "idx_students_cohort__dcbd29" ON "students" ("cohort_id", "status");
COMMENT ON COLUMN "students"."status" IS 'ENROLLED: ENROLLED\nCOMPLETED: COMPLETED\nDROPPED: DROPPED\nEARLY_EMPLOYED: EARLY_EMPLOYED\nTRANSFERRED: TRANSFERRED';
COMMENT ON COLUMN "students"."hrd_net_status" IS 'REGISTERED: REGISTERED\nTRAINING: TRAINING\nCOMPLETED: COMPLETED\nCOMPLETED_80_PERCENT: COMPLETED_80_PERCENT\nCOMPLETED_AND_EMPLOYED: COMPLETED_AND_EMPLOYED\nEARLY_EMPLOYED: EARLY_EMPLOYED\nWITHDRAWAL: WITHDRAWAL\nDROPPED_OUT: DROPPED_OUT\nLEAVE: LEAVE\nEXPELLED: EXPELLED';
        CREATE TABLE IF NOT EXISTS "student_rosters" (
    "id" UUID NOT NULL PRIMARY KEY,
    "airtable_record_id" VARCHAR(32) NOT NULL UNIQUE,
    "name" VARCHAR(50) NOT NULL,
    "phone_number" VARCHAR(11),
    "email" VARCHAR(255),
    "hrd_net_status" VARCHAR(30),
    "source_fields" JSONB NOT NULL,
    "is_removed_in_source" BOOL NOT NULL,
    "synced_at" TIMESTAMPTZ NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "cohort_id" UUID REFERENCES "cohorts" ("id") ON DELETE RESTRICT,
    "matched_student_id" UUID UNIQUE REFERENCES "students" ("id") ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS "idx_student_ros_name_5f66ed" ON "student_rosters" ("name", "phone_number");
CREATE INDEX IF NOT EXISTS "idx_student_ros_cohort__33ea95" ON "student_rosters" ("cohort_id");
COMMENT ON COLUMN "student_rosters"."hrd_net_status" IS 'REGISTERED: REGISTERED\nTRAINING: TRAINING\nCOMPLETED: COMPLETED\nCOMPLETED_80_PERCENT: COMPLETED_80_PERCENT\nCOMPLETED_AND_EMPLOYED: COMPLETED_AND_EMPLOYED\nEARLY_EMPLOYED: EARLY_EMPLOYED\nWITHDRAWAL: WITHDRAWAL\nDROPPED_OUT: DROPPED_OUT\nLEAVE: LEAVE\nEXPELLED: EXPELLED';
-- ---------------------------------------------------------------
-- raw SQL: DBML 제약·enum 값·기본값 (Tortoise로 표현할 수 없는 부분)
-- ---------------------------------------------------------------
ALTER TABLE "hrd_net_bootcamps"
    ALTER COLUMN "weekend_se" SET DEFAULT 'WEEKDAY',
    ALTER COLUMN "day_night_se" SET DEFAULT 'DAY',
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_hrd_net_bootcamps_train_type"
        CHECK ("train_type" IS NULL OR "train_type" IN ('KDT', 'KDC')),
    ADD CONSTRAINT "check_hrd_net_bootcamps_weekend_se"
        CHECK ("weekend_se" IN ('WEEKEND', 'WEEKDAY', 'HYBRID')),
    ADD CONSTRAINT "check_hrd_net_bootcamps_day_night_se"
        CHECK ("day_night_se" IN ('DAY', 'NIGHT', 'HYBRID'));
ALTER TABLE "hrd_net_bootcamp_cohorts"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_hrd_net_cohort_period"
        CHECK ("train_start_date" IS NULL OR "train_end_date" IS NULL
               OR "train_start_date" <= "train_end_date");
ALTER TABLE "bootcamps"
    ALTER COLUMN "is_active" SET DEFAULT true,
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now();
ALTER TABLE "cohorts"
    ALTER COLUMN "status" SET DEFAULT 'PLANNED',
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_cohort_period" CHECK ("start_date" <= "end_date"),
    ADD CONSTRAINT "check_cohorts_status"
        CHECK ("status" IN ('PLANNED', 'ONGOING', 'ENDED', 'INACTIVE', 'ARCHIVED'));
ALTER TABLE "students"
    ALTER COLUMN "status" SET DEFAULT 'ENROLLED',
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_students_period" CHECK ("ended_at" IS NULL OR "enrolled_at" <= "ended_at"),
    ADD CONSTRAINT "check_students_status"
        CHECK ("status" IN ('ENROLLED', 'COMPLETED', 'DROPPED', 'EARLY_EMPLOYED', 'TRANSFERRED')),
    ADD CONSTRAINT "check_students_hrd_net_status"
        CHECK ("hrd_net_status" IN ('REGISTERED', 'TRAINING', 'COMPLETED', 'COMPLETED_80_PERCENT',
               'COMPLETED_AND_EMPLOYED', 'EARLY_EMPLOYED', 'WITHDRAWAL', 'DROPPED_OUT', 'LEAVE',
               'EXPELLED'));
ALTER TABLE "student_rosters"
    ALTER COLUMN "is_removed_in_source" SET DEFAULT false,
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_student_rosters_phone_number"
        CHECK ("phone_number" IS NULL OR "phone_number" ~ '^01[0-9]{8,9}$'),
    ADD CONSTRAINT "check_student_rosters_hrd_net_status"
        CHECK ("hrd_net_status" IS NULL OR "hrd_net_status" IN ('REGISTERED', 'TRAINING',
               'COMPLETED', 'COMPLETED_80_PERCENT', 'COMPLETED_AND_EMPLOYED', 'EARLY_EMPLOYED',
               'WITHDRAWAL', 'DROPPED_OUT', 'LEAVE', 'EXPELLED'));
ALTER TABLE "roster_sync_runs"
    ALTER COLUMN "status" SET DEFAULT 'RUNNING',
    ALTER COLUMN "fetched_count" SET DEFAULT 0,
    ALTER COLUMN "upserted_count" SET DEFAULT 0,
    ALTER COLUMN "removed_count" SET DEFAULT 0,
    ALTER COLUMN "unmapped_count" SET DEFAULT 0,
    ADD CONSTRAINT "check_roster_sync_scope"
        CHECK (("scope_type" = 'ALL' AND "bootcamp_id" IS NULL AND "cohort_id" IS NULL)
            OR ("scope_type" = 'BOOTCAMP' AND "bootcamp_id" IS NOT NULL AND "cohort_id" IS NULL)
            OR ("scope_type" = 'COHORT' AND "bootcamp_id" IS NOT NULL AND "cohort_id" IS NOT NULL)),
    ADD CONSTRAINT "check_roster_sync_runs_trigger" CHECK ("trigger" IN ('SCHEDULED', 'MANUAL')),
    ADD CONSTRAINT "check_roster_sync_runs_status"
        CHECK ("status" IN ('RUNNING', 'SUCCEEDED', 'FAILED'));"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    # aerich 생성 순서는 FK 의존을 고려하지 않아 실패하므로, 참조하는 쪽부터 지우도록 바로잡았다
    return """
        DROP TABLE IF EXISTS "student_rosters";
        DROP TABLE IF EXISTS "roster_sync_runs";
        DROP TABLE IF EXISTS "students";
        DROP TABLE IF EXISTS "cohorts";
        DROP TABLE IF EXISTS "bootcamps";
        DROP TABLE IF EXISTS "hrd_net_bootcamp_cohorts";
        DROP TABLE IF EXISTS "hrd_net_bootcamps";"""


MODELS_STATE = (
    "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"
)
