from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "mentoring_balance_accounts" (
    "id" UUID NOT NULL PRIMARY KEY,
    "period_type" VARCHAR(30) NOT NULL,
    "valid_from" DATE NOT NULL,
    "valid_until" DATE NOT NULL,
    "total_minutes" INT NOT NULL,
    "held_minutes" INT NOT NULL,
    "used_minutes" INT NOT NULL,
    "remaining_minutes" INT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "student_id" UUID REFERENCES "students" ("id") ON DELETE RESTRICT,
    "team_id" UUID REFERENCES "mentoring_teams" ("id") ON DELETE RESTRICT
);
COMMENT ON COLUMN "mentoring_balance_accounts"."period_type" IS 'PROJECT_MENTORING: PROJECT_MENTORING\nREGULAR_MENTORING: REGULAR_MENTORING';
        CREATE TABLE IF NOT EXISTS "mentoring_balance_transactions" (
    "id" UUID NOT NULL PRIMARY KEY,
    "request_id" UUID,
    "type" VARCHAR(20) NOT NULL,
    "amount" INT NOT NULL,
    "after_remaining" INT NOT NULL,
    "after_held" INT NOT NULL,
    "reason" VARCHAR(100) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "account_id" UUID NOT NULL REFERENCES "mentoring_balance_accounts" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_mentoring_b_account_82d404" ON "mentoring_balance_transactions" ("account_id", "created_at");
COMMENT ON COLUMN "mentoring_balance_transactions"."type" IS 'STAFF_GRANT: STAFF_GRANT\nSTAFF_ADJUST: STAFF_ADJUST\nHOLD: HOLD\nRELEASE: RELEASE\nUSING: USING\nREFUND: REFUND';
-- raw SQL: 시간 계좌 (M8·M9·A39)
ALTER TABLE "mentoring_balance_accounts"
    ALTER COLUMN "total_minutes" SET DEFAULT 0,
    ALTER COLUMN "held_minutes" SET DEFAULT 0,
    ALTER COLUMN "used_minutes" SET DEFAULT 0,
    ALTER COLUMN "remaining_minutes" SET DEFAULT 0,
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_balance_period_type"
        CHECK ("period_type" IN ('PROJECT_MENTORING', 'REGULAR_MENTORING')),
    ADD CONSTRAINT "check_balance_owner_exists" CHECK (num_nonnulls("student_id", "team_id") = 1),
    ADD CONSTRAINT "check_balance_consistency"
        CHECK ("remaining_minutes" = "total_minutes" - "held_minutes" - "used_minutes"),
    ADD CONSTRAINT "check_balance_non_negative"
        CHECK ("remaining_minutes" >= 0 AND "held_minutes" >= 0 AND "used_minutes" >= 0),
    ADD CONSTRAINT "check_balance_validity" CHECK ("valid_from" <= "valid_until");
-- (소유자, 유형)당 계좌 하나
CREATE UNIQUE INDEX "uid_balance_student_period" ON "mentoring_balance_accounts" ("student_id", "period_type")
    WHERE "student_id" IS NOT NULL;
CREATE UNIQUE INDEX "uid_balance_team_period" ON "mentoring_balance_accounts" ("team_id", "period_type")
    WHERE "team_id" IS NOT NULL;
-- 원장 (append-only, M10)
ALTER TABLE "mentoring_balance_transactions"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_transaction_type"
        CHECK ("type" IN ('STAFF_GRANT', 'STAFF_ADJUST', 'HOLD', 'RELEASE', 'USING', 'REFUND')),
    ADD CONSTRAINT "check_transaction_amount" CHECK ("type" = 'STAFF_ADJUST' OR "amount" > 0),
    ADD CONSTRAINT "check_transaction_request"
        CHECK (("type" IN ('STAFF_GRANT', 'STAFF_ADJUST')) = ("request_id" IS NULL));
-- 같은 신청의 같은 처리는 한 번만 (request_id → mentoring_requests FK는 P11)
CREATE UNIQUE INDEX "uid_transaction_request_type" ON "mentoring_balance_transactions" ("request_id", "type")
    WHERE "request_id" IS NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "mentoring_balance_transactions";
        DROP TABLE IF EXISTS "mentoring_balance_accounts";"""


MODELS_STATE = (
    "eJztXWtz4jq2/SsUn3qqcrsCCd0Z6t5b5YA7oRtMLo9z+kwz5XJASTwNMmOb7s7MnP9+Jb"
    "8fkrGMIbLRl2CMtgJry9LW2g/9u7kxVmBtvR+BzSMwp/oz3G1H+Faz2/h3E2obgC7ojS4a"
    "TW27DZvgG7b2uHalnOaq5bR3PtIeLdvUljb69ElbWwDdWgFraepbWzcgugt36zW+aSxRQx"
    "0+h7d2UP/nDqi28QzsF2CiD779Hd3W4Qr8AhZ++625s9AH6ObSBJoNVqpmN1Gbb03L1uyd"
    "RfrEBKhTC99ZGi+Gie7iTrff1ScdrFcxDPQV7sC5r9qvW+fefD7of3Ja4i/9iDpZ7zYwbL"
    "19tV8MGDTf7fTVeyyDP3sGEJj4y0TAwL/VQ8+/5f5udMM2dyD4wavwxgo8abs1hrT53087"
    "uMRINpBS3lsvmglW7/WV9R6Cn6q++l/vW0YkVFUZz9SpPFPVJoMylgbEitShjZH/959uvy"
    "E2zt0m/ge9e2ny7urDXxw0DMt+Np0PHeSafzqCmq25oo4WQ8DdceOCl0K+h36cDHcbB/0B"
    "+jYaXIKUFhJdJNSBfkIRRfg3Qk2EY9kH1ocuP9jN6Wzel5VZt+FdLOAI/R1Pug33tZlLFc"
    "2N9ktdA/hsv6C37csM1fwmTRzttC8d7RjowXSfW8X7pO18hJUUKgXqy+/ONVEj5GchKlNI"
    "Bd5IP7IGcg/3OMZXeTC+omN8lcJ4pVvbtfaq4vfq1gRPwATe6C7yEGR0x7E2moo0krsN/H"
    "cBlUHvi/feuyryNLTyaKpF11QrpamNZi9fVDSl4V9UUD3JPnjWyUia9e7lPpqS3AukmbHq"
    "XCPNeFcLKI1uB3fz8XzabQSXfMxeoSFQaDUJpE+3kDQfZKU/UO4Yl25frNvwLpBWHh4m49"
    "+w8vyrBZzIn+XeDN/zr/jQkwl+6OCna6ellNVHENv6BpAXm4RoQlMrT/a9f8HNs1WGsTUb"
    "jOTpTBo94O43lvXPtYOXNJPxJ23n7mvi7rsPCb0EnTR+H8zuG/ht429jRU5acEG72d+a+D"
    "tpO9tQofFT1VZRTPzb/q2Env8Bljaa/DQLgcBgUqQEOZ41C9sV+QyLLMsi9WBF9j+Mz1Vc"
    "soTH6kR2dX700Q9cjeH61RsYFXnOvDGc+ZjttquCWo9LCq3zonXC7Op9++jkGuc2VDYGgy"
    "J+AKXB2XR7CGsRebYsYDIiGxEpkyCqLJyYcnv6TuSAfEYvDu0nwwT6M/wCXlMGewJQj7ic"
    "o24CwrKauIZ3wyfJ1H4GRGV0VCEA0G8FtgPBBM0jk0Fv1sycHEoAued0lBdmPieDvShTZk"
    "UK4nhkP2rL7z81c6XGhjj+xGgbiTtB2/RHm/YmeUeD2rODFP5J+Ad4ihhLO/tFWi6NHbSp"
    "XH660UUWl2+gleZF1dz2R+DyvzW3pvFDX7mPu/vf/DsYY4et92eDoOnfEy4AQd7zQt5HtV"
    "mEa4nKc03bf5G+SONuw3lZwLvx+G4odxvu6wIq0m/yBLOY6IUPaiX9aBE1RH4wiMI8q6fg"
    "3rvd6eTBvdOhA48/E3vveu/CxN77HLWeZ+8tdoViV8jFfoW2K+xJ057Ul99qixJCT9iaxP"
    "RC35Lgn3b8qCKxpeBlSwE2mr5msVYDgXIs1P2AV9s+fdGsF2RubDXL+mmYTPsCgmj9HHJH"
    "AZ05luqQOCreFrE4vp08e90Ofa/bSe11twgioMIdDkNlATkpV8pY5mj6aLXyBEK16IFQrS"
    "TSj7ppv6h4L0Le5ZBxjktl7XCqN3dkIIw3KAn80PpsGj+0tXpYhBKhGxGqdFw+zYW80AY/"
    "ISpClfjZ0Kd5HMeYVH8AU0c/p4i2iR0InfOsc9cOOEDnxA6EznnWuW6pGtoz/yAYMreGsQ"
    "YapGzwo3IJFT8iwWOtusGd0+r1djwexlR6O5glFs356FZGZqSjS9RId4mngTJLrKBrzbLV"
    "tfGswwJPWEpYPF08P10uAVlkKo1LCi3zrGXh6aSquaI+L+HpPEet0zydKdcc3YkUce6kss"
    "ET1pUn/+nLBKw1B+H0YMhKRK/YmKB58AjROtGwu+KgESP+6gLaMZ2VD8Dc6JaFvirVZZls"
    "cpHluNwGjYX78nzcl0s0EFicEH772jkvW7kS21oZiW2tdGJb9JulQJ6BXzZtVxETq4PTMs"
    "u2kL/OYmaFD+m7kfT1LzHTYjhW7vzmERX0huNbUmzO0aJIIhkLxhoQVsCRBl9nBv6bM+pn"
    "gvopvPy96WOUEfPj/DY1sSjFfqmJ7QNkYwfcZnwRejJMRx/fwasPthc2FKjK+ygU9BrYL6"
    "axe34JxBI9E8OO0H01in2whlMX4fDHEJbf2C+lL7zBEBJLrlhyz2nJLT+0QsStHBFcYcyc"
    "0pgRzGW+QV9NDovGXBbisJxoaoohykLF4Ajng+xQPh7L0mmYiOs9YZ4eZvMT6JlKreaslj"
    "/h9ybt/3AUxy3/lHmftP8jW4MyLP/wacxMFsg0/1OPU3bSgHqafcC3prU0tsAdi+gj9x3O"
    "ZRY7BF52CHENFQm5jPfAs3nbvEP2jjTsNtzXBbwdj2c9tHB2G/7VAvbG9+PJrNtwX5sFzO"
    "EjVO3zHxyGZyMqI0rWxPEEv7Y6+rRIDGNMUgRh8OOXFUEY57uVidX1Ca2zvFNlREQkHovq"
    "XmXDmZHHjUdeGlrmPO467qQvknWnwoc0R3UvkSBfYtm0t8mQvzUMe6lttlNbe3qi7nwJrS"
    "6ytr+PXnucIPb0dJQ6XmCzXRuvwBlW/r9zCAj8sCcLdn0Lm4hdMTe7YvK8nG8/7MtyvRMe"
    "SYp0hwtzeRcLKE2nA2R64fM3gks+dr/CjqdDX187Ppio2Sa/hJgwQJPUh7c4McKaEBOwZt"
    "v1URPgQBNU9rqquxmaGGE5bPyobXUgyL4VWXeQE7MjV/a+Wz0529pPtcm09b0Cxaex9MMq"
    "0hQ7X5yvJ6x8YeULK19Y+VGtFzmYo6zjOHjTs7DwOYNVWPhva+G/0ckcVQWY3wM5+mCrmf"
    "YGZBzHkWySadmvgsYim+V87HWkc6RxxnUtJiQCoUQSy8l2NJlJLHSMy0hi4RvqTq78505G"
    "/nMnnf9s7ohJCfRkoUBApAmJNCGxWxcFjs5R64RA2uIFjvwN3oG5YXXdDx+1RE8cNML+Ko"
    "UqfXcV06PYW53F3srVOd5RH5QMROiGZwO2OZHv5kNpgmuqOxc4/0eZTaSekwHkXi3gQJnJ"
    "E6XbcF8X8EGazFQ8s6qfx7fdRuztAn6ayPJQUnrY8RJeL2BfGgz/6DacF+Fz4XwSr+h6Lq"
    "y4c9Q6zYqLsxE+ZcpIoKUEhWsoecqOYel2mC+em5mMiwlYuU094qH0Qbnuy/ChLsG7RnDd"
    "VHPA7vWwpebCHE5M/zEv0VP84HVZd7gTMySzS5MQTR4GAxYnKMg5RzXRASk8pwzQSKGbdY"
    "EsTezsy0QcQzAz0J9T5CHysHqVnYVYClcWn0YzOLPUfLufO1P9uUuQaOdDor2tO52jcpvl"
    "U1VbUzdM3X5NwzvdaOv1AFK8vFG5BMy6a/xWbBFC3xe9/NdV++OHG/Sp8x3xm48ZiE9H0n"
    "CYPndK0H90lKtJBAn67xy1Lpy4NXPiTsCzjv8t/tKShQ8MygydzSOWz2g1Iz2oWtCFsGHP"
    "x4YVSXEiKa4KE3RF1+pKlL6oTnArgzvpTVMNa4lozFpgLLmYFhX+zz21AiOQlehLihqNdT"
    "PWL5I1BNOjjliinZcyI3zOGiVVGeEg0bOi+PKb50mfVHJuW4tuVk9xmIHvyYuY1qjNN7S9"
    "0eydlfxE7Gh52dGK0OYzDG0OH8oiug6lT6fi5oOs9AfKHePD5YshXbkXCyg9PEzGv8n9bs"
    "O/WsCJ/FnuzfA9/4oPPZnghw5+FqI4EqLiMAZ+3A9pTsME/wBLG63ZmsWWDp0SrEO6bvyp"
    "usqVD32VkQ99lc6HFtQhHf36UofCuVs3rYvcDpHbUT9Y+cntqCycGVSxOP2kxLhj8kRbAr"
    "wibUakzXCeNpMIATo8HGxPiFJNFHLUILG4EynjSCSG05BOQZ+/oB8Oga2K8474o8hF4kJQ"
    "mi4HE9PJKkyX4mHQU8cCrd++dtCWzx3rloqmK/0HAV80B66BBikTRlQugTOanY62EvnYn3"
    "ZauB2PhzEe43aQLPA3H93Kk3ctB3rUSHdNhXTCiKabztKheh7orQme9F8so5veQym0LkfD"
    "/QgziWB0a8btCUb3HLWeh9FNGsuMXBlFXPBm2bxZaouSgpyZe7g3Vwqwz+V8Mcq4O4CBcO"
    "2EUmpP1A38o7IMUcioB7HlPoPtKKevRZ9Sz5yEu80j+jh9+Jo/MMUhbG8x5V5kUA9xzaWw"
    "z87uTwmLFP9UGBzCB9t4ZOuRDGtcKstyrCC6GSBiyy95mhZcMcMXlTlr8KoYhDmUFMULjm"
    "QJwnTFug3vYgHHyt3YCcv0LhZQVvq4hfOCA2+l3mzwm4xDb92rBcR7/4EbuOldNfNNGMc+"
    "yUS3lgZaQZ93OuqQtERmHGdCkK0b13PVzhO/16aH77WTiAc8mQkc9NgwJ0sL1PehLhg2Ov"
    "TV5FoEw3aOWs/DsL15kj1vui4nsC++0S5IW4oDfguQlqXl0MYpy3pyZxcU4jJPai0nyeFV"
    "hbo8btiyd6vDQ9Ombi91g/2o7DB9iiBwxZnzCZ05TvkSjkglkxw/2ZSyIJAFgcztnFAige"
    "z0qhajkUmyB/KhnOVxstGhLh5FGOW05DnjaIH1k7rVXlVtY+xIqRjUx50gWeiB5ww+73lv"
    "t64/Xt9cfbgOHvrgTtaTLwpD158RETzYOWpdRJrxTtqISDMRacY/+CfkEnKyCAX4A1HE/H"
    "w4gbfNZ3trYyXmJW/lKi7Uyigu1EoXF/KfLbawhLhU3cIRjgK0u/F3MCICvT+KKt4Dx8Wz"
    "ml/6s24D/VnAL/0evuo1C6khlxYylJDUAVxaLdVim09CEY4RLzzQj4Bwmx3htkCYBeErdo"
    "SvBMK5Ef4JwHdM0NJA3j9Tx3s4Yczr77L8pS/9wWjiOWKy0u82vIsF9Dpy76CLBbz/43Yy"
    "QE3cVz7m85X2qkL9+cU+QFfJPk6orQKacnTi6EMZ3N2jVdZ54VM7tmFra9W1Wp4AQUFUcp"
    "8gKch9mkfvCR9RC0z1xdgRnKZ0jInCAmYCzJHRiHEiEEvZrmliBzVCuhTvdAQjNCUfhLEv"
    "LyAWvsBae4WEL/ActU7zBaacVHl8JTFOvbi3pK7OqkQBsBL8SucQk31UL9MEPSnAnL7C5W"
    "RHP5KI0Ooiy8dkOu1VCwmo5u4kpxA54XSR04fCsP/oJ8IVxYsrCv3P52dSYGpe+j4Q59k5"
    "1Zz27uX+fIhzl4PLBRxJylwaOkftotciBMMRTgZaGltwkEsl3gPXakEmfbeB/izg7Xg86y"
    "HroNvwr/CBUPfjiXMcFH7lRD3VqxkwmStKgYObPLFuw7tYwOm815Nlp0pAcLmAn6SB81y5"
    "r9xoySy2P4hL1nB/UN39QHob+KRD3XoppOeEqDidi2s9A3uJdbVkjKdPyZ0ufebySGotmw"
    "febS3gTHis2KYFBbhJcE2wMX4UwDYlJ6BNjVu4QduvIuM2JSjApYLrFughmLufp2NlD74R"
    "2eTqqi/txn8aa906GtKRXfrjTl/bOrTe4//3FrtzjFVspfUt13cj6WvSqO0Nx7fJJRR3cJ"
    "ss/GaahqlugGVpz4Sd4gz8ooz/lGAdomeyjB356ywb/cDWGY6VO795UiVx9N+8Okt18Gco"
    "zlKoKEtZxVhqg2hGWs8blgPhE96SqoGkB3EJCLN5USqKb56CNnSP3zE9MrG6KwRfTLIuC9"
    "0LE60Ds9f70lzslu3WzWKnLVudxmL3eP3UQn9vOqvG/zQkr3Aivq/ddNDfNrjBb24ukcTy"
    "qXONBVbLxrsVWOoW6tFqSK3Lv7xv4P4uL1Gbjze41+XNJWq67KwucR9/vW7gcwbdNg1lPh"
    "y+T9J4HH0tYoUU/0jJaAHtmF8q5ofCHKzjnQoSa9DzB2K1VIR3igfvlKgzup89L7/OqEhP"
    "O+IxSbGphgHkpFwdtm2JYO1WnmDtFj1Yu5XEGmw0fc0CciBQP3TbnU4eL1unQ3ez4c/IiZ"
    "aHeUXTvfA8kyDL9G4wnckT7PQMrxdwNpEGrsfUv8Iu7NHDUJ7hpsFl5K56c6k+yJOerMwi"
    "DSJ3o20lpa/K6M34j1h3sfsLKEuT4R+RdvH3C4i9Nf2J9DuOewivF7A/GT88oN7Gc/RVIm"
    "8WcChLuA6884L6//ogDx2Hr3+1gHPlizL+Xek2vIsiTuCrPDPtFX2mvUo7gY2duQS+XZEa"
    "m3QKMyV4EH/J2axwaqISB58V88RHBYV/lmf/rG6pvssKV9RzHp+0uvcdekrs4oTnnwZ3Kn"
    "sAagWDk2RlMh4O2U808eXwgSXuFW2x9dayYFHbv0Si5VuZfpInzgofeVNkWSs/tglA01iv"
    "M6ZUimkbFzvrg38A+pLs+K3KAq86KxHlxCkTaJabDpB7YxWTquHuKld1lXZGdZV2urqKyG"
    "2jo1/NLCeR23aOWqfltnHj++ZNz+WEE2CfECOgERERSpAZSuA73A50cs9RNzV3cUfGFL/h"
    "A5zOABWOH+gZ0PH0f9LXIOOc6mSji+zTqt3m6DusgSgYej5+cKxvldUtGxPi2aNS1F94jI"
    "qWDmjgF2EG3gO0J1NLnMsuouUAZun/IpHE+jM9nScqVqeTcP7abl9dfWxfXn246Vx//Ni5"
    "uQwi+NMfZYXy3w7uMCscUwSJJkafPgP1O3hlGeYJsXJGOkeBNK3L9nWukd6+zhjr+ENB49"
    "R7Q5+HxnEt0SJaj0sKzyc/rI2rZYaSREwbjOgm0LXzCcujJzqGYGagP/tL88ir3VJDM7e/"
    "1ajZbvtPxm0ZGQ7C1oyKG317BjwR1dffKQru+P8L/Vvf1o/ccqIG3VjnDYDojnutYxR3S+"
    "e92OXxsssLxs8h1V9SnfC8I2mOZGU2nnQb7usCDpTpbDLvOffC62YBa658xzvhSctrOhNE"
    "eVYLN8HSEdyYY3lJsjV0PB8jrDe1gBSDPZCt4VgvP1jd1u01E9KBQB3hPQa3V+yY4FIPCO"
    "YNdfbYH1b4SjwVuNrgVTA4sz+RPs0YbWhXCEdbopcFlHqzAc4ecF8XUFb6btCmUztuJk9G"
    "A0VyQjbDa07MPUHbnSFtJ6Kv6qb1PNFXIR/CGDCUEhRhQ/FZ1CXi8BZsuzZeAWDElyIuYt"
    "2SMDvkHiu4USExcMl7YCfWhjkuMy1bIr5v6jM9SjRh8jFPg80c/yZ7XdU9Ao4yQ+YINfQc"
    "AodDPXI6qpljKYVzdLLMgW7ExXI4woOgs5qjnLKnSojppMzpabX4TtXcEbaE4M0KTuU5gm"
    "zTy1kevRwUP5sc8gQXLeGpoDtnw5ElAmfPx6UK9eV35nJGEZn6OYzKr7Ox0q3tGh84i96r"
    "WxM8ARNAUgGAnGfX0rs7IfWpSCOZlfnEMt0G/otPsu198d57V0VYzfJDb1+AtlrrbC69qE"
    "z9HoijuJrQvzKN1W7px2bFoaZXZ07K1QHuLJ7wGMWZwa8tMG2d7Tj5mFAdUD9BfvrWNFyL"
    "cFMgmpwoXD/gRVC58FMI75TQ+iHeqTdLZOcrW6dE5plOH6XJogOPxj2H+Hsa30YuEsBIs7"
    "GUCOBywJZQIaA8Wi3K1RMotQSVT6fTXDpcUGmCShNUmqDSBJUmqLSmoNIElZYSqgPqgkrj"
    "AvhjUWm6pSLrVf9RoGR1KHfCOtW+oVnZMtXacgnQV4PPqgnQz7aIW+ws5MkdiFLhDDoQ/D"
    "F91qkmkyj443PUuuCPBX9cBVNO8Mf14I+9srLZLHK60UV2WVOniOupKOXoYaChDe/WxYma"
    "9EHmcrR8TlxGsNO8sNNbYOrGKih6U4QtTXTBc1WF5sNk/FnuzVS3bo5z6Fzq1gJO5Lv5UJ"
    "pEW6VuFeFSj3BWmyjNUOnSDHxaGzmxW6KpRrWAba8BnuXVrbHWlxQGbv80Qu+N6xllOpv3"
    "0ZygTuT/myO7odtI3HBKOcylodqfT6TZYKw4NR2iN/iYSbbaq4qwohRwzrEKROS5Vtj9eD"
    "4Z/tFtuK8L+CBPUNvp1FFN5M0CjsbK7B439S4WcDgfPajT+ajb8K+KKK/8mhsYfJM4i1GL"
    "QkdF6lQTut26/nh9c/XhOigFHdzJqgCdZvqgoVovxk8VA6VtjB0kPBpUdMnCp8P5siIgCx"
    "/CifnrFXBwK8hmpqVFmWV+CMw0bx3oC2GQefpgjpgYclccu0ub8teHwcQ7cXvgHDU+kpQ5"
    "PsDbfUXvnd2c2pedMltuPa30PT4MNOF5okNfTR+E8Dydo9bzeJ7EqYb1qvRUH0gzihGJI/"
    "gYq4PsP4KPg7JDVYU3T90hlmo4x3EFol96uzaW32doCc7lFkwLXOR2EeLAr0csrOIV/7QO"
    "Q89J5HgehP+PO/+fqxeihUmhDxNyZ+1E8sAAkDB690LoSZ01gK5D0t+HJDIVqDucuBQNwI"
    "rubvbsZmJbFuJ2JeQSblITAxbAu5OUK5RVBVEZoYADFZBF0JHhrwQPx1O+iCDR6OhXk04R"
    "JNo5al2QaILx4Q3bUhgfLiiJKbBxlpiVl5GIt79gIiQsT/bobITgHHjhHLT1Gk3kNtA24T"
    "hIqyA7k5HShchlZMkndUBsqQiwViH8Q1GBO1MMjvO11ZYBW+pGhzsbEJKdqLFlNHERXUYD"
    "2p0nCgOdFBdAJ4FG4KCNu7ZSX4ydSYB4ukETBhXntPTpEG5fHxfiq/bHDwG6+E0WsNORNB"
    "xS5mm0CV3tzCDpkQVfkvzpEL468iAuA2FMPG0BXGXXVtgziil9nA7pFv9A/wTg+0p7VQ2E"
    "lDelsuJM6aIQzEUI0A+XFRjQPkjLtWGBA4FO9nEypFut64pAjd0gBw5pQhcnA/r4WRllAn"
    "3omCb1IaAWbpJaE+bCTXKOWq+em4SHwiFlOElYePz9DhXmE/YOcqfwoIPynSkllP+eQ+2H"
    "pju4PTjBW3vqgVPaX+wvEK7uQlHVDRQ7RbxmGGPsxFZZeEIXwZrcOE5MsAWkxTlfBl8ofc"
    "Ii1mOlx1zEGst0G/jvAvalAc7Ad14W8HdZ/oLfuq/NfEv3kctZh08Ko9EUE6yhzVRdGylt"
    "GqM9YxEVR8SEgrlWsEd2WepGs74XZMpC4dp4iMogE9x1B1k0tr4mP0C04Na43FmXWkK/69"
    "kwmcqbR2XqFx5cfoK9CL8W4ddviH41GSbBK56j1vPwiiLh/tjh1yIjvCYZ4WFqt7bGmpKW"
    "S1wybg+7SGl/sZ9ddBLBXVFVc2VF/PX50Iii5nOlaz7/0NY6mpxMY8Oym45LnXW2uQsFMx"
    "+REDtrCG3D1tYFQqpTcrVhykqLpX7BjdiRTYoJYJPA7ixQBNikmAA2TfBuUN/YqGRHlygr"
    "IBYBeXWnUARxdo5az0OcWfZuhQ/AYNsXx6UO2B9z5pU4ZAscsVdxCh8boBERgWYmD+kNvR"
    "KIyKnbU83O6rtIEJHxRzVH6U88FEujedEvmKH+ao5x5OnlmuqdmRq0NIdbzE33pmQu2Chf"
    "O5Q/RVCpxzDj/xQxRkVYKTd8sJetyrg+xqXEEpkwOA4g1yvBqiMj99Mn9W4iKc6ZZ8GbBX"
    "TfSP3P82nwkftuAe/Hwz4+emvYx4z7UJamMubZnYsFnE8d3t15wZ9/mit9/DF+LcK9l3/Q"
    "FvNBUG9x+NMxt10l8xrakw1MNSCBWIBNSwqEqQi/eBAygesLCVyJpOeJowW5AzSRV5EvsS"
    "Irs0KEC9ae/8rDenr7BUZzNC4lQseyKZvInqwsUoESi1RNtPfyC/HhxifFcG+s9ZX2up9X"
    "iDW8yEcmvLgyIm7sfHgCT+XM56Un5cqOnOEhXz1n3IzzymAz+u1raDF28hiMHbq92BHmoj"
    "AXu8JJXj+t05zkBxVZOYJ95bjRwOYRmPtNrGTbnFaWV+Eayx3B0voWdZP5Xlz0279FXbrR"
    "UO+/C9uMU9vszQIceJvzynHfiBSJSqdICEuwbjZBHkvwjQPneNN0vWK9OEW3nGAvHgzZfC"
    "Ysq/F6FKs1daywv8g6Jg1amZG5nLJVg+p2IvKIL6vV01cK+eyaSwnROvmoyyi6JAzYShuw"
    "J+WJOQvAEzSx2ByUvzkQNHHdtJ4nl4qv4uZ8bFkOpMZEXSdxrC5XO+w8leDTA7gEeEXZrL"
    "flL6TdSreHxjOVuog3uMhiLTTcVF0bJziI+Bv6ryb6NGQt3LcuwtEUKeyJQ98CHwdgudtc"
    "kUDFI43h5tKx7NdCCZ631TzFgieembxAJ8RqiHb5G+TYfJTbmxwVEtmAcUQfwRMyLtJwfp"
    "6OFTKcoURyw6kv7cZ/GmvdquARdRloYihim0p/hL4bSV+Tg7c3HN8mYccd3JKSn1hgDwQE"
    "6sVR17csM7Tbun7E5XUnx7x83aHOy/gjQVwePsQ5p6xI+U++xc+cApUQFMvwniSo6NbqQD"
    "JgboHcVACf4ObIeUqMrxgbgL5FQ5kPh2/GBgBTX740STSA+8lF5v4/bMNNMhPV9018ugku"
    "b0+J3ObOlJOTTd+X/wCmxbgxj4jUcK/Y7uQxSlArekmMTsoswQ8VA8Je8xqie5wceAPaxI"
    "A7+iYmInLQNoY3tE+xj3nTHJM//x9dQiF5"
)
