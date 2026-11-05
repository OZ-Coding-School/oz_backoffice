from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    # student_rosters를 students로 합친다 (decisions A10).
    # students.name은 NOT NULL로 추가하므로 기존 students 행이 없어야 한다 (P5 동기화 전이라 비어 있음).
    return """
        ALTER TABLE "roster_sync_runs" ADD "unmapped_records" JSONB NOT NULL DEFAULT '[]'::jsonb;
        ALTER TABLE "students" ADD "airtable_record_id" VARCHAR(32) UNIQUE;
        ALTER TABLE "students" ADD "source_fields" JSONB;
        ALTER TABLE "students" ADD "synced_at" TIMESTAMPTZ;
        ALTER TABLE "students" ADD "is_removed_in_source" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "students" ADD "phone_number" VARCHAR(11);
        ALTER TABLE "students" ADD "name" VARCHAR(50) NOT NULL;
        ALTER TABLE "students" ADD "email" VARCHAR(255);
        ALTER TABLE "students" ALTER COLUMN "user_id" DROP NOT NULL;
        DROP TABLE IF EXISTS "student_rosters";
        CREATE INDEX IF NOT EXISTS "idx_students_name_a073af" ON "students" ("name", "phone_number");
ALTER TABLE "students"
    ADD CONSTRAINT "check_students_phone_number"
        CHECK ("phone_number" IS NULL OR "phone_number" ~ '^01[0-9]{8,9}$');"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    # aerich 생성물은 student_rosters를 되살리지 않아 1번 마이그레이션의 정의로 다시 만든다.
    # 가입 전 수강생(user_id NULL)이 있으면 SET NOT NULL이 실패한다 (명단 데이터는 되돌리지 않음).
    return """
        DROP INDEX IF EXISTS "idx_students_name_a073af";
        ALTER TABLE "students" DROP CONSTRAINT IF EXISTS "check_students_phone_number";
        ALTER TABLE "students" DROP COLUMN "airtable_record_id";
        ALTER TABLE "students" DROP COLUMN "source_fields";
        ALTER TABLE "students" DROP COLUMN "synced_at";
        ALTER TABLE "students" DROP COLUMN "is_removed_in_source";
        ALTER TABLE "students" DROP COLUMN "phone_number";
        ALTER TABLE "students" DROP COLUMN "name";
        ALTER TABLE "students" DROP COLUMN "email";
        ALTER TABLE "students" ALTER COLUMN "user_id" SET NOT NULL;
        ALTER TABLE "roster_sync_runs" DROP COLUMN "unmapped_records";
        CREATE TABLE IF NOT EXISTS "student_rosters" (
    "id" UUID NOT NULL PRIMARY KEY,
    "airtable_record_id" VARCHAR(32) NOT NULL UNIQUE,
    "name" VARCHAR(50) NOT NULL,
    "phone_number" VARCHAR(11),
    "email" VARCHAR(255),
    "hrd_net_status" VARCHAR(30),
    "source_fields" JSONB NOT NULL,
    "is_removed_in_source" BOOL NOT NULL DEFAULT false,
    "synced_at" TIMESTAMPTZ NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT now(),
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT now(),
    "cohort_id" UUID REFERENCES "cohorts" ("id") ON DELETE RESTRICT,
    "matched_student_id" UUID UNIQUE REFERENCES "students" ("id") ON DELETE SET NULL,
    CONSTRAINT "check_student_rosters_phone_number"
        CHECK ("phone_number" IS NULL OR "phone_number" ~ '^01[0-9]{8,9}$'),
    CONSTRAINT "check_student_rosters_hrd_net_status"
        CHECK ("hrd_net_status" IS NULL OR "hrd_net_status" IN ('REGISTERED', 'TRAINING',
               'COMPLETED', 'COMPLETED_80_PERCENT', 'COMPLETED_AND_EMPLOYED', 'EARLY_EMPLOYED',
               'WITHDRAWAL', 'DROPPED_OUT', 'LEAVE', 'EXPELLED'))
);
CREATE INDEX IF NOT EXISTS "idx_student_ros_name_5f66ed" ON "student_rosters" ("name", "phone_number");
CREATE INDEX IF NOT EXISTS "idx_student_ros_cohort__33ea95" ON "student_rosters" ("cohort_id");"""


MODELS_STATE = (
    "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"
    "rM32+UpMhOTwm8CPXI9JiQuHXMx+/R86kMB4"
)
