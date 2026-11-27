from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        -- 계약 개편 (A109): 운영 배포 전이라 개발 DB의 기존 계약과 계약이 없어지는 가입 전 멘토를 지운다
        DELETE FROM "educator_contracts";
        DELETE FROM "mentors" WHERE "user_id" IS NULL;
        ALTER TABLE "educator_contracts" DROP CONSTRAINT IF EXISTS "check_educator_contracts_educator_type";
        ALTER TABLE "educator_contracts" DROP CONSTRAINT IF EXISTS "check_educator_contracts_status";
        ALTER TABLE "educator_contracts" DROP CONSTRAINT IF EXISTS "check_contract_period";
        ALTER TABLE "educator_contracts" DROP CONSTRAINT IF EXISTS "check_contract_educator_type";
        ALTER TABLE "educator_contracts" DROP CONSTRAINT IF EXISTS "check_contract_file_required";
        CREATE TABLE IF NOT EXISTS "contract_amendments" (
    "id" UUID NOT NULL PRIMARY KEY,
    "amended_on" DATE NOT NULL,
    "reason" VARCHAR(500) NOT NULL,
    "before" JSONB NOT NULL,
    "after" JSONB NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "contract_id" UUID NOT NULL REFERENCES "educator_contracts" ("id") ON DELETE RESTRICT,
    "created_by_user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE RESTRICT,
    "contract_file_id" UUID UNIQUE REFERENCES "contract_files" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_contract_am_contrac_b283e2" ON "contract_amendments" ("contract_id", "created_at");
COMMENT ON TABLE "contract_amendments" IS '서명 후 변경 계약 이력 (A109⑨).';
        ALTER TABLE "educator_contracts" ADD "no_show_pay_amount" BIGINT;
        ALTER TABLE "educator_contracts" ADD "amount_note" VARCHAR(500);
        ALTER TABLE "educator_contracts" ADD "mentoring_time_basis" VARCHAR(20);
        ALTER TABLE "educator_contracts" ADD "cancel_reason" VARCHAR(500);
        ALTER TABLE "educator_contracts" ADD "unit_price" BIGINT;
        ALTER TABLE "educator_contracts" ADD "total_amount" BIGINT;
        ALTER TABLE "educator_contracts" ADD "business_registration_number" VARCHAR(10);
        ALTER TABLE "educator_contracts" ADD "settlement_type" VARCHAR(20) NOT NULL;
        ALTER TABLE "educator_contracts" ADD "termination_reason" VARCHAR(40);
        ALTER TABLE "educator_contracts" ADD "cohort_id" UUID;
        ALTER TABLE "educator_contracts" ADD "vat_type" VARCHAR(20) NOT NULL;
        ALTER TABLE "educator_contracts" ADD "price_unit" VARCHAR(20);
        ALTER TABLE "educator_contracts" ADD "contract_type" VARCHAR(20) NOT NULL;
        ALTER TABLE "educator_contracts" ADD "canceled_on" DATE;
        ALTER TABLE "educator_contracts" ADD "terminated_on" DATE;
        ALTER TABLE "educator_contracts" ADD "bootcamp_id" UUID NOT NULL;
        ALTER TABLE "educator_contracts" ADD "contact_person_name" VARCHAR(50);
        ALTER TABLE "educator_contracts" ADD "termination_detail" VARCHAR(500);
        ALTER TABLE "educator_contracts" DROP COLUMN "educator_type";
        COMMENT ON COLUMN "educator_contracts"."status" IS 'DRAFT: DRAFT\nIN_PROGRESS: IN_PROGRESS\nSIGNED: SIGNED\nACTIVE: ACTIVE\nENDED: ENDED\nCANCELED: CANCELED\nTERMINATED: TERMINATED';
        ALTER TABLE "educator_contracts" ALTER COLUMN "end_date" DROP NOT NULL;
        ALTER TABLE "educator_contracts" ALTER COLUMN "contractor_phone" DROP NOT NULL;
        ALTER TABLE "educator_contracts" ALTER COLUMN "start_date" DROP NOT NULL;
        COMMENT ON COLUMN educator_contracts."mentoring_time_basis" IS 'STUDENT_REQUEST: STUDENT_REQUEST\nACTUAL_DURATION: ACTUAL_DURATION';
COMMENT ON COLUMN educator_contracts."settlement_type" IS 'FIXED: FIXED\nUNIT_PRICE: UNIT_PRICE\nACTUAL_COST: ACTUAL_COST';
COMMENT ON COLUMN educator_contracts."termination_reason" IS 'TERMINATED_BY_FAULT: TERMINATED_BY_FAULT\nTERMINATED_BY_MUTUAL_AGREEMENT: TERMINATED_BY_MUTUAL_AGREEMENT\nTERMINATED_BY_UNILATERAL: TERMINATED_BY_UNILATERAL';
COMMENT ON COLUMN educator_contracts."vat_type" IS 'INCLUDED: INCLUDED\nEXCLUDED: EXCLUDED\nNOT_APPLICABLE: NOT_APPLICABLE';
COMMENT ON COLUMN educator_contracts."price_unit" IS 'HOURLY: HOURLY\nPER_SESSION: PER_SESSION\nDAILY: DAILY\nMONTHLY: MONTHLY\nPER_ITEM: PER_ITEM';
COMMENT ON COLUMN educator_contracts."contract_type" IS 'MENTOR: MENTOR\nINSTRUCTOR: INSTRUCTOR\nSW: SW\nEQUIPMENT: EQUIPMENT\nOTHER: OTHER';
        ALTER TABLE "educator_contracts" ADD CONSTRAINT "fk_educator_cohorts_8ed54805" FOREIGN KEY ("cohort_id") REFERENCES "cohorts" ("id") ON DELETE RESTRICT;
        ALTER TABLE "educator_contracts" ADD CONSTRAINT "fk_educator_bootcamp_2a15b9bf" FOREIGN KEY ("bootcamp_id") REFERENCES "bootcamps" ("id") ON DELETE RESTRICT;
        CREATE INDEX IF NOT EXISTS "idx_educator_co_status_0965ee" ON "educator_contracts" ("status", "start_date");
        CREATE INDEX IF NOT EXISTS "idx_educator_co_bootcam_b94461" ON "educator_contracts" ("bootcamp_id", "cohort_id");
        ALTER TABLE "educator_contracts"
            ADD CONSTRAINT "check_educator_contracts_contract_type"
                CHECK ("contract_type" IN ('MENTOR', 'INSTRUCTOR', 'SW', 'EQUIPMENT', 'OTHER')),
            ADD CONSTRAINT "check_educator_contracts_status"
                CHECK ("status" IN ('DRAFT', 'IN_PROGRESS', 'SIGNED', 'ACTIVE', 'ENDED', 'CANCELED', 'TERMINATED')),
            ADD CONSTRAINT "check_educator_contracts_settlement_type"
                CHECK ("settlement_type" IN ('FIXED', 'UNIT_PRICE', 'ACTUAL_COST')),
            ADD CONSTRAINT "check_educator_contracts_price_unit"
                CHECK ("price_unit" IS NULL OR "price_unit" IN ('HOURLY', 'PER_SESSION', 'DAILY', 'MONTHLY', 'PER_ITEM')),
            ADD CONSTRAINT "check_educator_contracts_vat_type"
                CHECK ("vat_type" IN ('INCLUDED', 'EXCLUDED', 'NOT_APPLICABLE')),
            ADD CONSTRAINT "check_educator_contracts_mentoring_time_basis"
                CHECK ("mentoring_time_basis" IS NULL OR "mentoring_time_basis" IN ('STUDENT_REQUEST', 'ACTUAL_DURATION')),
            ADD CONSTRAINT "check_educator_contracts_termination_reason"
                CHECK ("termination_reason" IS NULL OR "termination_reason" IN ('TERMINATED_BY_FAULT', 'TERMINATED_BY_MUTUAL_AGREEMENT', 'TERMINATED_BY_UNILATERAL')),
            ADD CONSTRAINT "check_contract_period"
                CHECK ("start_date" IS NULL OR "end_date" IS NULL OR "start_date" <= "end_date"),
            ADD CONSTRAINT "check_contract_type_link"
                CHECK (("contract_type" = 'MENTOR' OR "mentor_id" IS NULL) AND ("contract_type" = 'INSTRUCTOR' OR "instructor_id" IS NULL)),
            ADD CONSTRAINT "check_contract_file_required"
                CHECK ("status" IN ('DRAFT', 'CANCELED') OR "contract_file_id" IS NOT NULL),
            ADD CONSTRAINT "check_contract_amount"
                CHECK (("settlement_type" = 'FIXED' AND "total_amount" IS NOT NULL AND "unit_price" IS NULL AND "price_unit" IS NULL)
                    OR ("settlement_type" = 'UNIT_PRICE' AND "unit_price" IS NOT NULL AND "price_unit" IS NOT NULL)
                    OR ("settlement_type" = 'ACTUAL_COST' AND "unit_price" IS NULL AND "price_unit" IS NULL)),
            ADD CONSTRAINT "check_contract_amount_non_negative"
                CHECK (coalesce("total_amount", 0) >= 0 AND coalesce("unit_price", 0) >= 0 AND coalesce("no_show_pay_amount", 0) >= 0),
            ADD CONSTRAINT "check_contract_mentor_terms"
                CHECK (("contract_type" = 'MENTOR') = ("no_show_pay_amount" IS NOT NULL)
                    AND ("contract_type" = 'MENTOR') = ("mentoring_time_basis" IS NOT NULL)
                    AND ("contract_type" <> 'MENTOR' OR ("settlement_type" = 'UNIT_PRICE' AND "price_unit" IN ('HOURLY', 'PER_SESSION')))),
            ADD CONSTRAINT "check_contract_party"
                CHECK (("contract_type" IN ('MENTOR', 'INSTRUCTOR') AND "contractor_phone" ~ '^01[0-9]{8,9}$'
                        AND "business_registration_number" IS NULL AND "contact_person_name" IS NULL)
                    OR ("contract_type" NOT IN ('MENTOR', 'INSTRUCTOR')
                        AND ("contractor_phone" IS NULL OR "contractor_phone" ~ '^[0-9]{9,11}$'))),
            ADD CONSTRAINT "check_contract_business_number"
                CHECK ("business_registration_number" IS NULL OR "business_registration_number" ~ '^[0-9]{10}$'),
            ADD CONSTRAINT "check_contract_cancel"
                CHECK (("status" = 'CANCELED') = ("cancel_reason" IS NOT NULL AND "canceled_on" IS NOT NULL)
                    AND ("status" = 'CANCELED' OR ("cancel_reason" IS NULL AND "canceled_on" IS NULL))),
            ADD CONSTRAINT "check_contract_termination"
                CHECK (("status" = 'TERMINATED') = ("termination_reason" IS NOT NULL AND "terminated_on" IS NOT NULL)
                    AND ("status" = 'TERMINATED' OR ("termination_reason" IS NULL AND "termination_detail" IS NULL AND "terminated_on" IS NULL)));"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DELETE FROM "contract_amendments";
        DELETE FROM "educator_contracts";
        DELETE FROM "mentors" WHERE "user_id" IS NULL;
        ALTER TABLE "educator_contracts"
            DROP CONSTRAINT IF EXISTS "check_educator_contracts_contract_type",
            DROP CONSTRAINT IF EXISTS "check_educator_contracts_status",
            DROP CONSTRAINT IF EXISTS "check_educator_contracts_settlement_type",
            DROP CONSTRAINT IF EXISTS "check_educator_contracts_price_unit",
            DROP CONSTRAINT IF EXISTS "check_educator_contracts_vat_type",
            DROP CONSTRAINT IF EXISTS "check_educator_contracts_mentoring_time_basis",
            DROP CONSTRAINT IF EXISTS "check_educator_contracts_termination_reason",
            DROP CONSTRAINT IF EXISTS "check_contract_period",
            DROP CONSTRAINT IF EXISTS "check_contract_type_link",
            DROP CONSTRAINT IF EXISTS "check_contract_file_required",
            DROP CONSTRAINT IF EXISTS "check_contract_amount",
            DROP CONSTRAINT IF EXISTS "check_contract_amount_non_negative",
            DROP CONSTRAINT IF EXISTS "check_contract_mentor_terms",
            DROP CONSTRAINT IF EXISTS "check_contract_party",
            DROP CONSTRAINT IF EXISTS "check_contract_business_number",
            DROP CONSTRAINT IF EXISTS "check_contract_cancel",
            DROP CONSTRAINT IF EXISTS "check_contract_termination";
        DROP INDEX IF EXISTS "idx_educator_co_bootcam_b94461";
        DROP INDEX IF EXISTS "idx_educator_co_status_0965ee";
        ALTER TABLE "educator_contracts" DROP CONSTRAINT IF EXISTS "fk_educator_bootcamp_2a15b9bf";
        ALTER TABLE "educator_contracts" DROP CONSTRAINT IF EXISTS "fk_educator_cohorts_8ed54805";
        ALTER TABLE "educator_contracts" ADD "educator_type" VARCHAR(20) NOT NULL;
        ALTER TABLE "educator_contracts" DROP COLUMN "no_show_pay_amount";
        ALTER TABLE "educator_contracts" DROP COLUMN "amount_note";
        ALTER TABLE "educator_contracts" DROP COLUMN "mentoring_time_basis";
        ALTER TABLE "educator_contracts" DROP COLUMN "cancel_reason";
        ALTER TABLE "educator_contracts" DROP COLUMN "unit_price";
        ALTER TABLE "educator_contracts" DROP COLUMN "total_amount";
        ALTER TABLE "educator_contracts" DROP COLUMN "business_registration_number";
        ALTER TABLE "educator_contracts" DROP COLUMN "settlement_type";
        ALTER TABLE "educator_contracts" DROP COLUMN "termination_reason";
        ALTER TABLE "educator_contracts" DROP COLUMN "cohort_id";
        ALTER TABLE "educator_contracts" DROP COLUMN "vat_type";
        ALTER TABLE "educator_contracts" DROP COLUMN "price_unit";
        ALTER TABLE "educator_contracts" DROP COLUMN "contract_type";
        ALTER TABLE "educator_contracts" DROP COLUMN "canceled_on";
        ALTER TABLE "educator_contracts" DROP COLUMN "terminated_on";
        ALTER TABLE "educator_contracts" DROP COLUMN "bootcamp_id";
        ALTER TABLE "educator_contracts" DROP COLUMN "contact_person_name";
        ALTER TABLE "educator_contracts" DROP COLUMN "termination_detail";
        COMMENT ON COLUMN "educator_contracts"."status" IS 'DRAFT: DRAFT\nACTIVE: ACTIVE\nENDED: ENDED\nTERMINATED: TERMINATED';
        ALTER TABLE "educator_contracts" ALTER COLUMN "end_date" SET NOT NULL;
        ALTER TABLE "educator_contracts" ALTER COLUMN "contractor_phone" SET NOT NULL;
        ALTER TABLE "educator_contracts" ALTER COLUMN "start_date" SET NOT NULL;
        COMMENT ON COLUMN educator_contracts."educator_type" IS 'MENTOR: MENTOR\nINSTRUCTOR: INSTRUCTOR';
        DROP TABLE IF EXISTS "contract_amendments";
        ALTER TABLE "educator_contracts"
            ADD CONSTRAINT "check_educator_contracts_educator_type" CHECK ("educator_type" IN ('MENTOR', 'INSTRUCTOR')),
            ADD CONSTRAINT "check_educator_contracts_status" CHECK ("status" IN ('DRAFT', 'ACTIVE', 'ENDED', 'TERMINATED')),
            ADD CONSTRAINT "check_contract_period" CHECK ("start_date" <= "end_date"),
            ADD CONSTRAINT "check_contract_educator_type"
                CHECK (("educator_type" = 'MENTOR' OR "mentor_id" IS NULL) AND ("educator_type" = 'INSTRUCTOR' OR "instructor_id" IS NULL)),
            ADD CONSTRAINT "check_contract_file_required" CHECK ("status" = 'DRAFT' OR "contract_file_id" IS NOT NULL);"""


MODELS_STATE = (
    "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"
    "=="
)
