from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    # 멘토링 유형(평시/프로젝트) 제거 (decisions A41). 운영 데이터는 아직 없지만, 데이터가 있어도
    # 안전하게: 중복 활성 배정은 최근 것만 남기고 비활성화, 팀 번호는 기수별로 다시 매기며,
    # 한 수강생의 팀 소속·계좌가 둘 이상이면 자동으로 합치지 않고 중단한다(수동 정리 필요).
    return """
        DO $$
        BEGIN
            IF EXISTS (SELECT student_id FROM mentoring_team_members GROUP BY student_id HAVING count(*) > 1) THEN
                RAISE EXCEPTION '한 수강생이 두 팀에 속해 있습니다. 유형 제거 전에 정리하세요.';
            END IF;
            IF EXISTS (SELECT student_id FROM mentoring_balance_accounts WHERE student_id IS NOT NULL
                       GROUP BY student_id HAVING count(*) > 1)
               OR EXISTS (SELECT team_id FROM mentoring_balance_accounts WHERE team_id IS NOT NULL
                          GROUP BY team_id HAVING count(*) > 1) THEN
                RAISE EXCEPTION '한 소유자의 시간 계좌가 둘 이상입니다. 유형 제거 전에 정리하세요.';
            END IF;
        END $$;
        -- 같은 (멘토, 기수)의 활성 배정이 둘 이상이면 가장 최근 것만 남긴다
        UPDATE "cohort_mentors" SET "is_active" = false, "deactivated_at" = now(), "deactivation_reason" = 'MANUAL'
        WHERE "id" IN (
            SELECT "id" FROM (
                SELECT "id", row_number() OVER (
                    PARTITION BY "mentor_id", "cohort_id" ORDER BY "created_at" DESC, "id" DESC
                ) AS rn
                FROM "cohort_mentors" WHERE "is_active"
            ) ranked WHERE rn > 1
        );
        -- 팀 번호를 기수별로 다시 매긴다 (유형별 번호가 겹칠 수 있음). 임시로 음수를 쓰므로 check를 잠시 뗀다
        ALTER TABLE "mentoring_teams" DROP CONSTRAINT IF EXISTS "check_team_number";
        UPDATE "mentoring_teams" t SET "team_number" = - ranked.rn
        FROM (
            SELECT "id", row_number() OVER (
                PARTITION BY "cohort_id" ORDER BY "team_number", "created_at", "id"
            ) AS rn FROM "mentoring_teams"
        ) ranked WHERE t."id" = ranked."id";
        UPDATE "mentoring_teams" SET "team_number" = - "team_number";
        ALTER TABLE "mentoring_teams" ADD CONSTRAINT "check_team_number" CHECK ("team_number" > 0);
        -- 유형 컬럼을 지우면 그 컬럼을 쓰던 제약·인덱스도 함께 지워진다
        ALTER TABLE "mentoring_team_members" DROP CONSTRAINT IF EXISTS "fk_team_members_team";
        ALTER TABLE "mentoring_teams" DROP CONSTRAINT IF EXISTS "uid_mentoring_t_cohort__152ab3";
        ALTER TABLE "mentoring_team_members" DROP CONSTRAINT IF EXISTS "uid_mentoring_t_student_e1ec95";
        ALTER TABLE "cohort_mentors" DROP COLUMN "period_type";
        ALTER TABLE "mentoring_balance_accounts" DROP COLUMN "period_type";
        ALTER TABLE "mentoring_team_members" DROP COLUMN "period_type";
        ALTER TABLE "mentoring_teams" DROP COLUMN "period_type";
        -- 다시 거는 제약 (A41)
        CREATE UNIQUE INDEX "uid_cohort_mentors_active" ON "cohort_mentors" ("mentor_id", "cohort_id")
            WHERE "is_active";
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_mentoring_t_cohort__4bf4a2" ON "mentoring_teams" ("cohort_id", "team_number");
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_mentoring_t_student_1c76af" ON "mentoring_team_members" ("student_id");
        ALTER TABLE "mentoring_team_members" ADD CONSTRAINT "fk_team_members_team" FOREIGN KEY ("team_id")
            REFERENCES "mentoring_teams" ("id") ON DELETE CASCADE;
        CREATE UNIQUE INDEX "uid_balance_student" ON "mentoring_balance_accounts" ("student_id")
            WHERE "student_id" IS NOT NULL;
        CREATE UNIQUE INDEX "uid_balance_team" ON "mentoring_balance_accounts" ("team_id")
            WHERE "team_id" IS NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    # 되돌리면 모든 행을 평시(REGULAR_MENTORING)로 본다
    return """
        DROP INDEX IF EXISTS "uid_balance_student";
        DROP INDEX IF EXISTS "uid_balance_team";
        ALTER TABLE "mentoring_team_members" DROP CONSTRAINT IF EXISTS "fk_team_members_team";
        DROP INDEX IF EXISTS "uid_mentoring_t_student_1c76af";
        DROP INDEX IF EXISTS "uid_mentoring_t_cohort__4bf4a2";
        DROP INDEX IF EXISTS "uid_cohort_mentors_active";
        ALTER TABLE "cohort_mentors" ADD "period_type" VARCHAR(30) NOT NULL DEFAULT 'REGULAR_MENTORING';
        ALTER TABLE "mentoring_teams" ADD "period_type" VARCHAR(30) NOT NULL DEFAULT 'REGULAR_MENTORING';
        ALTER TABLE "mentoring_team_members" ADD "period_type" VARCHAR(30) NOT NULL DEFAULT 'REGULAR_MENTORING';
        ALTER TABLE "mentoring_balance_accounts" ADD "period_type" VARCHAR(30) NOT NULL DEFAULT 'REGULAR_MENTORING';
        ALTER TABLE "cohort_mentors" ALTER COLUMN "period_type" DROP DEFAULT,
            ADD CONSTRAINT "check_cohort_mentors_period_type"
                CHECK ("period_type" IN ('PROJECT_MENTORING', 'REGULAR_MENTORING'));
        ALTER TABLE "mentoring_teams" ALTER COLUMN "period_type" DROP DEFAULT,
            ADD CONSTRAINT "check_team_period_type"
                CHECK ("period_type" IN ('PROJECT_MENTORING', 'REGULAR_MENTORING')),
            ADD CONSTRAINT "uid_mentoring_teams_id_period" UNIQUE ("id", "period_type");
        ALTER TABLE "mentoring_team_members" ALTER COLUMN "period_type" DROP DEFAULT,
            ADD CONSTRAINT "fk_team_members_team" FOREIGN KEY ("team_id", "period_type")
                REFERENCES "mentoring_teams" ("id", "period_type") ON DELETE CASCADE;
        ALTER TABLE "mentoring_balance_accounts" ALTER COLUMN "period_type" DROP DEFAULT,
            ADD CONSTRAINT "check_balance_period_type"
                CHECK ("period_type" IN ('PROJECT_MENTORING', 'REGULAR_MENTORING'));
        CREATE UNIQUE INDEX "uid_cohort_mentors_active" ON "cohort_mentors" ("mentor_id", "cohort_id", "period_type")
            WHERE "is_active";
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_mentoring_t_cohort__152ab3" ON "mentoring_teams" ("cohort_id", "period_type", "team_number");
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_mentoring_t_student_e1ec95" ON "mentoring_team_members" ("student_id", "period_type");
        CREATE UNIQUE INDEX "uid_balance_student_period" ON "mentoring_balance_accounts" ("student_id", "period_type")
            WHERE "student_id" IS NOT NULL;
        CREATE UNIQUE INDEX "uid_balance_team_period" ON "mentoring_balance_accounts" ("team_id", "period_type")
            WHERE "team_id" IS NOT NULL;"""


MODELS_STATE = (
    "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"
    "3Bje0D6FH/Omeex//T8fHeAM"
)
