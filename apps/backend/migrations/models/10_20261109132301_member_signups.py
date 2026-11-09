from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "member_signups" (
    "id" UUID NOT NULL PRIMARY KEY,
    "signup_type" VARCHAR(20) NOT NULL,
    "nickname" VARCHAR(30),
    "display_name_preference" VARCHAR(10),
    "match_result" VARCHAR(20),
    "status" VARCHAR(20) NOT NULL,
    "reviewed_at" TIMESTAMPTZ,
    "reject_reason" VARCHAR(300),
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "requested_cohort_id" UUID REFERENCES "cohorts" ("id") ON DELETE RESTRICT,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_member_sign_user_id_30ee56" ON "member_signups" ("user_id", "created_at");
CREATE INDEX IF NOT EXISTS "idx_member_sign_status_e6d725" ON "member_signups" ("status", "created_at");
CREATE INDEX IF NOT EXISTS "idx_member_sign_request_74ad3d" ON "member_signups" ("requested_cohort_id");
COMMENT ON COLUMN "member_signups"."signup_type" IS 'STUDENT: STUDENT\nMENTOR: MENTOR';
COMMENT ON COLUMN "member_signups"."display_name_preference" IS 'NAME: NAME\nNICKNAME: NICKNAME';
COMMENT ON COLUMN "member_signups"."match_result" IS 'MATCHED: MATCHED\nNO_MATCH: NO_MATCH\nAMBIGUOUS: AMBIGUOUS';
COMMENT ON COLUMN "member_signups"."status" IS 'PENDING: PENDING\nAPPROVED: APPROVED\nREJECTED: REJECTED';
-- raw SQL: DB 기본값, enum·DBML check 제약, 회원당 대기 신청 하나(부분 유니크)
ALTER TABLE "member_signups"
    ALTER COLUMN "status" SET DEFAULT 'PENDING',
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_member_signups_signup_type"
        CHECK ("signup_type" IN ('STUDENT', 'MENTOR')),
    ADD CONSTRAINT "check_member_signups_status"
        CHECK ("status" IN ('PENDING', 'APPROVED', 'REJECTED')),
    ADD CONSTRAINT "check_member_signups_match_result"
        CHECK ("match_result" IS NULL OR "match_result" IN ('MATCHED', 'NO_MATCH', 'AMBIGUOUS')),
    ADD CONSTRAINT "check_member_signups_display_name_preference"
        CHECK ("display_name_preference" IS NULL
            OR "display_name_preference" IN ('NAME', 'NICKNAME')),
    ADD CONSTRAINT "check_member_signups_reviewed"
        CHECK (("status" = 'PENDING') = ("reviewed_at" IS NULL)),
    ADD CONSTRAINT "check_member_signups_reject_reason"
        CHECK ("status" = 'REJECTED' OR "reject_reason" IS NULL),
    ADD CONSTRAINT "check_member_signups_cohort"
        CHECK (("signup_type" = 'STUDENT') = ("requested_cohort_id" IS NOT NULL)),
    ADD CONSTRAINT "check_member_signups_mentor_fields"
        CHECK ("signup_type" = 'MENTOR' OR ("nickname" IS NULL AND "display_name_preference" IS NULL)),
    ADD CONSTRAINT "check_member_signups_display_nickname"
        CHECK ("display_name_preference" IS NULL OR "display_name_preference" = 'NAME'
            OR "nickname" IS NOT NULL);
CREATE UNIQUE INDEX "uid_member_signups_pending_user"
    ON "member_signups" ("user_id") WHERE "status" = 'PENDING';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "uid_member_signups_pending_user";
        DROP TABLE IF EXISTS "member_signups";"""


MODELS_STATE = (
    "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"
)
