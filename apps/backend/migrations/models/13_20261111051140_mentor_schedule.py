from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "mentor_unavailable_periods" (
    "id" UUID NOT NULL PRIMARY KEY,
    "repeat" VARCHAR(10) NOT NULL,
    "starts_at" TIMESTAMPTZ NOT NULL,
    "ends_at" TIMESTAMPTZ NOT NULL,
    "weekdays_mask" SMALLINT NOT NULL,
    "repeat_until" DATE,
    "category" VARCHAR(30),
    "reason" VARCHAR(200),
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "mentor_id" UUID NOT NULL REFERENCES "mentors" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_mentor_unav_mentor__676a1f" ON "mentor_unavailable_periods" ("mentor_id", "starts_at");
COMMENT ON COLUMN "mentor_unavailable_periods"."repeat" IS 'ONCE: ONCE\nDAILY: DAILY\nWEEKLY: WEEKLY';
        ALTER TABLE "mentors" ADD "accepting_requests" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "cohort_mentoring_settings" ADD "weekend_open_minute" SMALLINT;
        ALTER TABLE "cohort_mentoring_settings" ADD "weekday_close_minute" SMALLINT DEFAULT 1140;
        ALTER TABLE "cohort_mentoring_settings" ADD "weekend_close_minute" SMALLINT;
        ALTER TABLE "cohort_mentoring_settings" ADD "weekday_open_minute" SMALLINT DEFAULT 600;
-- raw SQL: 멘토 불가 시간 (A37)
ALTER TABLE "mentor_unavailable_periods"
    ALTER COLUMN "repeat" SET DEFAULT 'ONCE',
    ALTER COLUMN "weekdays_mask" SET DEFAULT 0,
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_unavailable_repeat" CHECK ("repeat" IN ('ONCE', 'DAILY', 'WEEKLY')),
    ADD CONSTRAINT "check_unavailable_range" CHECK ("starts_at" < "ends_at"),
    -- 30분 경계 (한국 시각 오프셋이 정시라 UTC 기준으로 검사해도 같다)
    ADD CONSTRAINT "check_unavailable_slot"
        CHECK (extract(epoch FROM "starts_at")::bigint % 1800 = 0
           AND extract(epoch FROM "ends_at")::bigint % 1800 = 0),
    -- 매주 반복만 요일(비트 1~127), 나머지는 0
    ADD CONSTRAINT "check_unavailable_weekdays"
        CHECK (("repeat" = 'WEEKLY' AND "weekdays_mask" BETWEEN 1 AND 127)
            OR ("repeat" <> 'WEEKLY' AND "weekdays_mask" = 0)),
    -- 일회성은 반복 종료일이 없고, 반복 한 회차는 24시간 이하
    ADD CONSTRAINT "check_unavailable_repeat_rule"
        CHECK (("repeat" = 'ONCE' AND "repeat_until" IS NULL)
            OR ("repeat" <> 'ONCE' AND "ends_at" - "starts_at" <= interval '1 day'));
-- raw SQL: 기수 운영시간 (자정부터 지난 분, 둘 다 NULL이면 운영 안 함, A37)
ALTER TABLE "cohort_mentoring_settings"
    ADD CONSTRAINT "check_settings_weekday_hours" CHECK (
        ("weekday_open_minute" IS NULL AND "weekday_close_minute" IS NULL)
        OR ("weekday_open_minute" IS NOT NULL AND "weekday_close_minute" IS NOT NULL AND "weekday_open_minute" >= 0 AND "weekday_open_minute" < "weekday_close_minute"
            AND "weekday_close_minute" <= 1440
            AND "weekday_open_minute" % 30 = 0 AND "weekday_close_minute" % 30 = 0)),
    ADD CONSTRAINT "check_settings_weekend_hours" CHECK (
        ("weekend_open_minute" IS NULL AND "weekend_close_minute" IS NULL)
        OR ("weekend_open_minute" IS NOT NULL AND "weekend_close_minute" IS NOT NULL AND "weekend_open_minute" >= 0 AND "weekend_open_minute" < "weekend_close_minute"
            AND "weekend_close_minute" <= 1440
            AND "weekend_open_minute" % 30 = 0 AND "weekend_close_minute" % 30 = 0));"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "cohort_mentoring_settings" DROP CONSTRAINT IF EXISTS "check_settings_weekday_hours";
        ALTER TABLE "cohort_mentoring_settings" DROP CONSTRAINT IF EXISTS "check_settings_weekend_hours";
        ALTER TABLE "mentors" DROP COLUMN "accepting_requests";
        ALTER TABLE "cohort_mentoring_settings" DROP COLUMN "weekend_open_minute";
        ALTER TABLE "cohort_mentoring_settings" DROP COLUMN "weekday_close_minute";
        ALTER TABLE "cohort_mentoring_settings" DROP COLUMN "weekend_close_minute";
        ALTER TABLE "cohort_mentoring_settings" DROP COLUMN "weekday_open_minute";
        DROP TABLE IF EXISTS "mentor_unavailable_periods";"""


MODELS_STATE = (
    "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"
    "Mw=="
)
