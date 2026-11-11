from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "mentoring_requests" (
    "id" UUID NOT NULL PRIMARY KEY,
    "replaced_request_id" UUID UNIQUE,
    "topic" VARCHAR(100) NOT NULL,
    "detail" TEXT NOT NULL,
    "desired_at_1" TIMESTAMPTZ NOT NULL,
    "desired_at_2" TIMESTAMPTZ,
    "desired_at_3" TIMESTAMPTZ,
    "duration" SMALLINT NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "rejected_at" TIMESTAMPTZ,
    "reject_reason" VARCHAR(300),
    "canceled_at" TIMESTAMPTZ,
    "cancel_reason" VARCHAR(300),
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "mentor_id" UUID NOT NULL REFERENCES "mentors" ("id") ON DELETE RESTRICT,
    "requester_id" UUID NOT NULL REFERENCES "students" ("id") ON DELETE RESTRICT,
    "team_id" UUID REFERENCES "mentoring_teams" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_mentoring_r_mentor__675f59" ON "mentoring_requests" ("mentor_id", "status");
CREATE INDEX IF NOT EXISTS "idx_mentoring_r_request_b1b800" ON "mentoring_requests" ("requester_id", "created_at");
CREATE INDEX IF NOT EXISTS "idx_mentoring_r_team_id_db2820" ON "mentoring_requests" ("team_id");
CREATE INDEX IF NOT EXISTS "idx_mentoring_r_status_4b83b2" ON "mentoring_requests" ("status");
COMMENT ON COLUMN "mentoring_requests"."status" IS 'PENDING: PENDING\nAPPROVED: APPROVED\nREJECTED: REJECTED\nCANCELED: CANCELED';
-- raw SQL: 멘토링 신청 (A42)
ALTER TABLE "mentoring_requests"
    ALTER COLUMN "status" SET DEFAULT 'PENDING',
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "fk_request_replaced" FOREIGN KEY ("replaced_request_id")
        REFERENCES "mentoring_requests" ("id") ON DELETE RESTRICT,
    ADD CONSTRAINT "check_request_status"
        CHECK ("status" IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELED')),
    ADD CONSTRAINT "check_request_duration" CHECK ("duration" > 0 AND "duration" <= 120 AND "duration" % 30 = 0),
    ADD CONSTRAINT "check_request_detail" CHECK (char_length("detail") BETWEEN 1 AND 2000),
    ADD CONSTRAINT "check_request_desired" CHECK ("desired_at_3" IS NULL OR "desired_at_2" IS NOT NULL),
    -- 반려·취소는 시각과 사유가 함께 (사유 필수, A42)
    ADD CONSTRAINT "check_request_rejected"
        CHECK (("status" = 'REJECTED') = ("rejected_at" IS NOT NULL)
           AND ("rejected_at" IS NULL) = ("reject_reason" IS NULL)),
    ADD CONSTRAINT "check_request_canceled"
        CHECK (("status" = 'CANCELED') = ("canceled_at" IS NOT NULL)
           AND ("canceled_at" IS NULL) = ("cancel_reason" IS NULL));
-- 원장의 원인 신청 FK (P10-2a에서 미룬 것)
ALTER TABLE "mentoring_balance_transactions"
    ADD CONSTRAINT "fk_transaction_request" FOREIGN KEY ("request_id")
        REFERENCES "mentoring_requests" ("id") ON DELETE RESTRICT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "mentoring_balance_transactions" DROP CONSTRAINT IF EXISTS "fk_transaction_request";
        DROP TABLE IF EXISTS "mentoring_requests";"""


MODELS_STATE = (
    "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"
)
