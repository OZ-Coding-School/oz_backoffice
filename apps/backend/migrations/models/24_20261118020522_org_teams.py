from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "teams" (
    "id" UUID NOT NULL PRIMARY KEY,
    "name" VARCHAR(20) NOT NULL,
    "description" VARCHAR(500),
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "department_id" UUID NOT NULL REFERENCES "departments" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_teams_departm_ead144" UNIQUE ("department_id", "name")
);
        CREATE TABLE IF NOT EXISTS "team_bootcamps" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL,
    "team_id" UUID NOT NULL REFERENCES "teams" ("id") ON DELETE RESTRICT,
    "bootcamp_id" UUID NOT NULL UNIQUE REFERENCES "bootcamps" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_team_bootca_team_id_7c3c6b" ON "team_bootcamps" ("team_id");
        ALTER TABLE "employees" ADD "team_id" UUID;
        ALTER TABLE "employee_positions" ADD "assignment_scope" VARCHAR(20);
        ALTER TABLE "employee_registrations" ADD "team_id" UUID;
        COMMENT ON COLUMN employee_positions."assignment_scope" IS 'COURSE: COURSE\nCOHORT: COHORT';
        ALTER TABLE "employees" ADD CONSTRAINT "fk_employee_teams_710ce355" FOREIGN KEY ("team_id") REFERENCES "teams" ("id") ON DELETE RESTRICT;
        ALTER TABLE "employee_registrations" ADD CONSTRAINT "fk_employee_teams_bb46d223" FOREIGN KEY ("team_id") REFERENCES "teams" ("id") ON DELETE RESTRICT;
ALTER TABLE "employee_positions"
    ADD CONSTRAINT "check_employee_positions_assignment_scope"
        CHECK ("assignment_scope" IS NULL OR "assignment_scope" IN ('COURSE', 'COHORT'));
-- A62: 상위 부서 트리를 없앤다. 기존 데이터는 옮기지 않는다(하위 부서는 부서로 남는다).
-- 개발 데이터는 `python -m app.cli seed-dev-org`로 넣는다 (마이그레이션에서 데이터를 넣지 않는다).
        ALTER TABLE "departments" DROP COLUMN "parent_id";
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_departments_name_c8865f" ON "departments" ("name");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "uid_departments_name_c8865f";
        ALTER TABLE "departments" ADD "parent_id" UUID;
ALTER TABLE "departments"
    ADD CONSTRAINT "fk_departments_parent"
        FOREIGN KEY ("parent_id") REFERENCES "departments" ("id") ON DELETE RESTRICT,
    ADD CONSTRAINT "check_departments_parent_not_self" CHECK ("parent_id" IS NULL OR "parent_id" <> "id");
CREATE UNIQUE INDEX "uid_departments_parent_name"
    ON "departments" ("parent_id", "name") NULLS NOT DISTINCT;
        ALTER TABLE "employee_registrations" DROP CONSTRAINT IF EXISTS "fk_employee_teams_bb46d223";
        ALTER TABLE "employees" DROP CONSTRAINT IF EXISTS "fk_employee_teams_710ce355";
        ALTER TABLE "employees" DROP COLUMN "team_id";
        ALTER TABLE "employee_positions" DROP CONSTRAINT IF EXISTS "check_employee_positions_assignment_scope";
        ALTER TABLE "employee_positions" DROP COLUMN "assignment_scope";
        ALTER TABLE "employee_registrations" DROP COLUMN "team_id";
        DROP TABLE IF EXISTS "team_bootcamps";
        DROP TABLE IF EXISTS "teams";"""


MODELS_STATE = (
    "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"
)
