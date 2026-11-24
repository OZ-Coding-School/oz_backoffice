from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "position_permissions" (
    "id" UUID NOT NULL PRIMARY KEY,
    "permission_code" VARCHAR(100) NOT NULL,
    "position_id" UUID NOT NULL REFERENCES "employee_positions" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_position_pe_positio_bb46f3" UNIQUE ("position_id", "permission_code")
);
COMMENT ON TABLE "position_permissions" IS '직위의 권한 묶음 (A87). 권한 코드는 access/domain/catalog.py가 정의한다.';
        ALTER TABLE "users" ADD "is_super_admin" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "employee_positions" ADD "data_scope" VARCHAR(20) NOT NULL DEFAULT 'ASSIGNED';
        COMMENT ON COLUMN employee_positions."data_scope" IS 'ASSIGNED: ASSIGNED\nALL: ALL';
        ALTER TABLE "employee_positions" ADD CONSTRAINT "check_employee_position_data_scope"
            CHECK ("data_scope" IN ('ASSIGNED', 'ALL'));
        -- 직위 = 역할(A87): 역할 테이블을 지운다. 데이터는 옮기지 않는다(운영 배포 전, A88)
        DROP TABLE IF EXISTS "user_roles";
        DROP TABLE IF EXISTS "role_permissions";
        DROP TABLE IF EXISTS "permissions";
        DROP TABLE IF EXISTS "roles";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "users" DROP COLUMN "is_super_admin";
        ALTER TABLE "employee_positions" DROP CONSTRAINT IF EXISTS "check_employee_position_data_scope";
        ALTER TABLE "employee_positions" DROP COLUMN "data_scope";
        DROP TABLE IF EXISTS "position_permissions";
        -- 역할 테이블을 5·30 마이그레이션 상태로 되돌린다 (데이터는 없음)
        CREATE TABLE IF NOT EXISTS "permissions" (
            "id" UUID NOT NULL PRIMARY KEY,
            "code" VARCHAR(100) NOT NULL UNIQUE,
            "description" TEXT
        );
        CREATE TABLE IF NOT EXISTS "roles" (
            "id" UUID NOT NULL PRIMARY KEY,
            "code" VARCHAR(50) NOT NULL UNIQUE,
            "name" VARCHAR(50) NOT NULL,
            "description" TEXT,
            "created_at" TIMESTAMPTZ NOT NULL DEFAULT now(),
            "scope_kind" VARCHAR(20),
            CONSTRAINT "check_role_scope_kind" CHECK (
                "scope_kind" IS NULL OR "scope_kind" IN ('GLOBAL', 'SCOPED')
            )
        );
        CREATE TABLE IF NOT EXISTS "user_roles" (
            "id" UUID NOT NULL PRIMARY KEY,
            "scope_type" VARCHAR(20) NOT NULL,
            "scope_id" UUID,
            "expires_at" TIMESTAMPTZ,
            "created_at" TIMESTAMPTZ NOT NULL DEFAULT now(),
            "role_id" UUID NOT NULL REFERENCES "roles" ("id") ON DELETE RESTRICT,
            "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE RESTRICT,
            CONSTRAINT "check_user_roles_scope_type"
                CHECK ("scope_type" IN ('GLOBAL', 'BOOTCAMP', 'COHORT')),
            CONSTRAINT "check_user_role_scope" CHECK (("scope_type" = 'GLOBAL') = ("scope_id" IS NULL))
        );
        CREATE INDEX IF NOT EXISTS "idx_user_roles_scope_t_eaa2fd"
            ON "user_roles" ("scope_type", "scope_id");
        CREATE UNIQUE INDEX "uid_user_roles_user_role_scope"
            ON "user_roles" ("user_id", "role_id", "scope_type", "scope_id") NULLS NOT DISTINCT;
        CREATE TABLE "role_permissions" (
            "permission_id" UUID NOT NULL REFERENCES "permissions" ("id") ON DELETE CASCADE,
            "role_id" UUID NOT NULL REFERENCES "roles" ("id") ON DELETE CASCADE,
            CONSTRAINT "pk_role_permissions" PRIMARY KEY ("role_id", "permission_id")
        );"""


MODELS_STATE = (
    "eJztXW1zo7iW/iuUP/VUZXtjJ+5kXLtbRRySeNovuX6Zmd7mFkWwknDbBl/A3Z29d/77Sr"
    "yZFwkjDI7A+hJjrKPYz5HEOc85OvpXa20uwcr+OALrJ2DN9BdjuxmhW62e8K+Woa4BvCA3"
    "OhNa6maza4JuOOrTypNymyu22979SH2yHUvVHPjps7qyAby1BLZm6RtHNw1419iuVuimqc"
    "GGuvGyu7U19H9ugeKYL8B5BRb84Ovf4W3dWIKfwEZvv7a2NvwA3tQsoDpgqahOC7b52rId"
    "1dnauE8sADu10R3NfDUteBd1uvmmPOtgtYxhoC9RB+59xXnbuPcWi8HtndsSfekn2Mlquz"
    "Z2rTdvzqtphM23W335Ecmgz16AASz0ZSJgoN/qoxfc8n43vOFYWxD+4OXuxhI8q9sVgrT1"
    "X89bQ0NIClApH+1X1QLLj/rS/miAH4q+/B//W0YkFGU8mSszaa4oLQplaKaBFKkbDkL+X3"
    "95/e6wce+20D/oP4jTDxeffnHRMG3nxXI/dJFr/eUKqo7qibpa3AHujRsPvBTyffjjJGO7"
    "dtEfwG+jGhpIaSHRRUId8CcUUURwY6eJ3VgOgA2gyw92azZf3ErjeU/wL2RjBP9Opj3Be2"
    "3lUkVrrf5UVsB4cV7h2855hmp+F6eudjrnrnZMODG9eTv2P+m4HyEl7ZRi6No39xqrEfxc"
    "iMoUUoE/0ivWQO7hHsf4Ig/GF2SML1IYL3V7s1LfFPRe2VjgGVjAH91FJkFGdwxrozUWR1"
    "JPQH9lYzzof/bf+1dFZkM7j6baZE21U5paq472qsAlDf2igupJ9sGyTkbivP8g3cIlybuA"
    "mpko7jXUjH8lG+LoZnC/mCxmPSG8ZGP12hkChZ4mofTxHiStR2l8OxjfUz66A7Ge4F9ArT"
    "w+Tie/I+UFV7IxlX6T+nN0L7hiQ08W+K6DH56dllLWLYTY0dcA/7BJiCY0tfRlPwYXzMyt"
    "Moyt+WAkzebi6BF1v7btf65cvMS5hD7puHffEnc/fEroJexE+GMwfxDQW+F/J2MpacGF7e"
    "b/20LfSd06pmKYPxR1GcUkuB3cSuj5H0Bz4OKn2hAECpMiJcjwqlnYrshnWGRZFqmJFfF/"
    "KOdVXLKEaXUkuzo/+vAHLifG6s0fGDWZZ/4Yzpxm282yoNbjklzrrGgds7r63z66uMa5DY"
    "WOwSCIH0BpMLbcHsJaROaWDSxKZCMiZRJEtYUTUW7P37AcUMDoxaG9My2gvxifwVvKYE8A"
    "6hOXC9hNSFjWE9fd3d1MstQfIVEZHVUQAPhbgeNCMIXryHTQn7cyF4cSQO67HeWFmc3FYC"
    "/KhFWRgDga2U+q9u2Hai2V2BBHn5gdM3EnbJv+aN1ZJ++ohvriIoV+EvoBviIm4tZ5FTXN"
    "3BoOkctPNzrL4vJN+KR5VVSvfQVc/tfWxjK/60tvunv/LbiDMHbZ+mA1CJv+PREC4OQ9K+"
    "R9VJtFuJaoPNO0/WfxszjpCe6LbNxPJvdDqSd4r7IxFn+XpojFhC9sUCvpqYXVEH5iYIVZ"
    "Vk9B37vT7ebBvdslA48+4753s70w7nufotbz+N7cK+ReIRP+Cskr7IuzvngrvZeLsoMe45"
    "rE9EJ2SdBPqz6riLsUrLgUYK3qKxprNRQox0LdD3i97dNX1X6F5sZGte0fpkXlF2BEmxeQ"
    "qwR06lyqQ/KoWHuIxfHt5vF1u2Rft5vydX266qAUwmQfLAO/N4dQNqBde3eHPocvRQiJ8n"
    "OoNhBOoEA9PJHYIvxMSMqVsuAwtMa323mQbpORbieRftIt51VBDiPeFcXjHJfKckPrt8Bn"
    "IIy8yORyskHMl7pSDksjw3TD88mqJT09yAuxMAlRnk/GDuuSJttci1/5Diwd/pwi2sZ2wH"
    "XOss49O+AAnWM74DpnWee6raiao3/HGDI3prkCqkFgYaJyCRU/QcGqnrrhnePq9WYyGcZU"
    "ejOYJx6ai9GNBM1IV5ewke6xg4PxPPEEXam2o6zMF90oMMNSwnx2sTy7PJa4yFIal+RaZl"
    "nLcC20txtgQZm1jkm+37eQJoT5akqxmvJUAKICahoU5qkAp6h1UipAKnZNjrJGop+pcgmJ"
    "BdmXv/s8BSvVRTg9GLIqNdRsTJBC3Jh0tmheanHQsCmxTQGtymg+NBUcTV1vZo76/EwM62"
    "NanWXF95/89ognfX6uJOcYrDcr8w24K2bw79C1BU2fVHLx110TXiWEmawAV1UpyPMx8YEs"
    "0zG9kTgW71ESsX8hG+JsNoAPJRTnCy/Z4Nm5Xds0CyePXRsu1HSLX0KMJz0mJlPwcKKENS"
    "HGYc3OJY2aAAfmk0p+V02zHc8SOaWJEZZjt2HUtjoQ5MCKbDrIidWRqQ2G3k7PbGs/1SbT"
    "1vc3Ux7H0t/teCXY+bwWILfyuZXPrXxu5Ue1XqSISFmlQ1jTM7fwGYOVW/jva+G/UxWRug"
    "LMbvGQW7BRLWcNMkqHJJtkWvbLsDHfq3c69vr7bmtiaBdH+dZ39GtRIJwQY9kZKrx/LN8G"
    "sqwdZOlKtNsVwISV5+Cng8c5FGjCBsgs90X6cx7zXAIYP4zEP3+JeS/Dyfg+aB6BvT+c3H"
    "DPknuWPC+qcVovNS8qcEYOzO5pqu8Wm0oOUNcH4jSHXTQOoyo9pvjAwvhLqZFH9pZiY537"
    "SifhK3k6Rx7yQYUKMN2wbOS3ptL9YihO0VZh90I2+pPxfCr25z0huJKNwXguTcc9wXuVjU"
    "dxOlfQ00f5bXLTE2JvZeNuKklDcdxHgZTdtWzcioPhl57gvvAYCuOLeE1tHm7pnqLWSZZu"
    "nLEJKFDKQE9KkId6ksVjTFtH/5kS2IQYhzUBK3IjKCGNiPAjIlg9IuJdifFKgru7JbKE2C"
    "MmsFXP6b83/ph6suQI8aIZXgLINPwCm8vBXnQja2EOXIOHUQnYBkzDo99l04dx4jlOHUjH"
    "7GHYpaAWp9DwO90aogNcUlgZoOEShpsCWZp+3FfMemKAuQn/5Jz4B5WyZsEqKOF4o/IZ3f"
    "gymsHsptbb/QyvEqxdnOo9HaqXp8VURqhuLN20dOctDe9sra5WA4OQrxGVS8Cse05FzR5C"
    "8PvCl/+46Fx9uoafut8RvbnKQHw2EofDdJka1UbFKFwvwdbMA2ooY/phOD2m1Z8spjMJhS"
    "HQKwpMPEymblgCvbIRQHDXmIO0Eu/hiCVo0XaW+7FfG5ZCLYGctyEGXckGHLfw7XDIhlJ4"
    "VIcMfT35fR7VOUWt8/yld+ITNsBa69Ba8N2i4mgFHtlj2GHjcDtGTtMUvOjo36IvLYZW3F"
    "5/OEvsLJd3bEV6UHb2I3eWT8dZ5nu++Z7vOizQNbVxalHZic0A4IH5AO+6k76RiMasBTpc"
    "MaI8HSg75yIKWYlB66jR2DRj/SwRzcKMOvzxrIxU0WJz1SipiBYDdQxqii+7ZQzIi0pOt7"
    "Wos1q9h/o1TBmImNawzdfW7kC56Cfco2XFo+U7fU5wp89hh0XyMyKPpScLfNfBj0IUR0KU"
    "n3vETtgmzWlY4B9Ac+AzW7XpKqikBBlOYSiYlnORq4TKRUYJlYt0CRVOHZLRby51yIPiTd"
    "M6KSjOtzryrY71hZVvdWzmVsfawplBvOO3ilBTkwdtFmED1xK2i+AfWyXAy3eR8l2kfBdp"
    "jYAubxdpIlHt8GTPPYl0DVFIpamMpExQTBwoI2mUHAUKR08id3VvDKglb7VftTb8e3V+if"
    "52rwV5qy6vNXm77HY1+Obp6eIT+uRSEz6I11e/fEw20J67UPTpcglvPXV+vRRUTQO2/Z9L"
    "cw3x/U9NddSV+fJx8wbltPNzJHHd7nr/zOsEyYHLj0kOlrkvhz3VJ7ro7eCHA2yZPtaHh8"
    "FYCYMlNZVCn8zBYkRZDn0VpGHbuWjYdgYN207TsJw/OIaLxs2wSsywMB/qfbJJkLcRT5nC"
    "WA/pRpl2g2veBwlKx8gacT0vng3CzGOQx8XIj8N6RkjyxMXejW9mTcflEM7vvkOhwDrGJK"
    "gZNs07UHaMDtYSODsaAyZP6jdloaiDj09mYXhXcXjywfZhpl2Y0x6s5OjjeHDD/XKcG2HV"
    "KHzfClHvbfY19+g0xmJQRzg5jbs3ZPSb697wtL+maZ2n/bHki/FMlUozVfIE+WOcbfEQP5"
    "Yubgj8lQb09xLxFCT8Mfn3V/jDDeCEnD/n4rnbxQCnknQFcnkCGY5Ayg+gDPGXG9dnCNry"
    "/VndVuBypX/H4AvXwBVQDcKCEZVL4AxXp8qeRAH2x10WbiaTYcyOvhkkj6JejG6k6Ye2Cz"
    "1spHtmAaYgsm65jw7FL3ywscCz/pNmdJN7KIVWYGi4V7CScEahYb4lZxROUet5GIWksUzJ"
    "KxDEObuQzS6kXJQU5NQcw4O1HAOnqY7uWYJnIIy7A9gGz04o5WylpoFfKcsQhQzDMSQQJT"
    "MMEf2VHdiNzlLfnDS26yf4cTK+uyMf/PpmnHpghnqIay6FffbpNSlhfoRNqvoSxAfZeHjr"
    "EQ9rXCrLcqwhuhkgIssvASAwltTwRWVOGrw61v4aiuMCZ/P4Yj3Bv5CNyfh+4lYD8y9kQx"
    "rfohbuC6r3Jvbng98lVPHNu5IN5PsPvHph/lUr34JRdeKIbmsmfIK+bHXYIe4RmZE9gpFt"
    "Gtdz0clTNqpDrhrVSSIe8mQWcNGjwxwvzVHfhzpn2MjQ15Nr4QzbKWo9D8PG3s4Jdk07ig"
    "0pcUe7IG1Z1mEPzYE4B2lZWun2OGXZTO7sjEBc5qnozsiZBHWFujxu2Ha2y8Nrzcy8XpoG"
    "e6XsMHmJwHDFmesJmTlOxRIqpJJxgZ9sSpkTyJxAZnZNKJFAdntVitHIONkD+VDG9hHR0a"
    "EeHkUY5bTkKeNog9WzslHfFHVtbnE7AYjTHSNZaMIzBp8/3zvty6vL64tPl+GkD+9kzfz0"
    "pOc8GBnqejIinAc7Ra3zTDPWSRueacYzzdgH/4hcQk4WoQB/UP0eN84JsMIJ8DIi1RZTDe"
    "YWXVpCXKpp6QiVAO05/i5GWKD3Z1HFe2C4eEvr8+28J8A/svH5to+u+q1CasilhQwlJHVg"
    "aHZbsenWk50Iw4gXHugVINyhR7jDEaZB+IIe4QuOcG6EfwDwDRG0JJD3r9TxHo6Y8/qHJH"
    "2+Fb9QmniumDS+7Qn+hWz4HXl34IVsPHy5mQ5gE++VjfV8qb4phv7y6hygq2QfR9RWAU25"
    "OnH1MR7cP8CnrPvCpnYc01FXime1PAOMgojkPkaSk/ukiB4ECJ3YoryaW0zQlIwxVpjDjI"
    "E5MhoRThhiKTs0je2gQUiXEp2OYASX5IMwDuQ5xDwW2OioEI8FnqLWSbHAVJAqT6ykpBqA"
    "TQ1WJQqAlRBXOoWc7EqjTFM4U4A1ezO06ZZ8AiKm1VlWjMly2ys2FFCsbc6DDw8JMX319m"
    "Z76yv87Gtrl/Yf/YSHolgJRcH/+fKCS0zNS9+H4iwHp1qz/oN0uxiivcvhpWyMxPFCHPYE"
    "77UIwVD+ZmZbMzfgoJBKvAem1QJN+p4A/8jGzWQy70ProCcEV7LRnzxMpvOe4L0yop761Q"
    "yYLsbjwfielpXzxXqCfyEbs0W/L0lulYDwUjbuxIE7r7xXZrRkFfMP4pIN9A/q6w+k3cBn"
    "3dDt10J6ToiWoGjGOJZG6Rk4GtKVRplPn5I73vaZ84rUWjYPvN3YwF3waLFNC3Jwk+BaYG"
    "1+L4BtSo5Dmxq3xhq6X0XGbUqQg0sE1yvQgzF3f5tNxnvwjcgmn6665gj/Fla6XRnSES/9"
    "aauvHN2wP6L/9x7eOcIq9qQNLNcPI/HPpFHbH05uko9Q1MFNsvCbZZmWsga2rb5gPMU5+E"
    "kY/ynBJmTPZBk70p/zbPRDW2c4Gd8HzZMqYexc2/rgT1GcpVBRlrKKsTQG0YxtPe9YDoRN"
    "eEuqBpIexCUgTBdFqSm+eQrakCN+VUZkYnVXMLGYZF0WchQmWgdmb/SlJW+1Tvta3qpauy"
    "vI26fL5zb8e91dCv8tiH7hRHRfve7Cvx1wjd5cn0MJ7bl7iQSWmvBhCTTdhj3agtg+/+Wj"
    "gPo7P4dtrq5Rr9r1OWyqdZfnqI9fL4UtdOa8NsJ4MRx+TNJ4DH0tbIUU1LB1Fs6+dIXtWB"
    "wKcbBudCrcWAPnH4jVUuHRKRaiU7zO6H72vPw6o3x7WoXHJMWWGgqQk3JNcNsSydrtPMna"
    "bXKydjuJNVir+ooG5FCgeeh2ut08UbZulxxmQ5/hN1oeFhVN98LySgIt0/vBbC5NUdBzdy"
    "0b86k48CKmwRUKYY8eh9IcNQ0vI3eV63PlUZr2pfE80iByN9pWHN8qEnwz+RLrLnZfNiRx"
    "OvwSaRd/LxsoWnM7Ff9AeQ+7a9m4nU4eH2FvkwX8KpE3sjGURFQH3n2B/f/5KA3dgG9wJR"
    "uL8efx5I9xT/AvigSBL/KstBfklfYiHQQ2t5YGArsiNTbJFGZK8CD+krFV4dhEJUo+KxaJ"
    "jwry+CzL8VndVoKQFaqo506ftLr3HXqK7eKI55+Gd2p7AGoNk5Ok8XQyHNKfaBLIoQNLvC"
    "vSw9Z/loUPtf2PSPj4Hs/upKn7hI+8KfJYKz+3CRiWuVplLKkE0zYudtIH/wD4JenxW5YF"
    "Xn2eRIQTpyyg2t52gNyOVUyqgd5VruoqnYzqKp10dRW+t42Mfj13OfG9baeoddLeNmZi36"
    "zpuZx0AhQTogQ0IsJTCTJTCYKA24FB7gXspuEh7siYYjd9gNEVoMb5A33TcCP9d/oKZJxT"
    "nWx0ln1atdccfocV4AVDTycOjvSt0IZlY0IsR1SKxgurqGjpggZ+YlbgPUD7Mo3EuewiWi"
    "5gtv5/OJJYfyFv54mKNekknF87nYuLq875xafr7uXVVff6PMzgT3+Ulcp/M7hHrHBMETia"
    "GH76ApRv4I1mmCfEyhnpDCXStM87l7lGeucyY6yjDzmN02yHPg+N41miRbQel+SRT3ZYG0"
    "/LFCWJqByMqBPo2fmYx6MvOjHA3IR/9pfmkZZbTYUrd+BqNMzb/ovSLcPDgXHNiLiR3TPg"
    "iyiB/o5RcCf4X/DfBrZ+5JabNejlOq+BAe941zpCcau577mXx4qXF46fQ6q/pDph2SNpja"
    "TxfDLtCd6rbAzGs/l00Xfv7a5bBay58gPvmJmW13TGiLKsFmaSpSO4Uefy4mQbGHiuIq03"
    "9QApBnso28CxXn6yuqM7KyqkQ4EmwlsFt1fsmOBSDwhmDXX63B9a+Eo8Fbje4NUwOfN2Kt"
    "7NKW1oTwhlW8IX2RD78wHaPeC9yoY0vvWSNt3acXNpOhqMRTdlc3fNiLnHabsTpO149lXT"
    "tJ4n+2rHh1AmDKUEedpQfBX1iDjkgm1W5hsAlPgSxHmuWxJml9yjBTcqxAcu3gd2c22o8z"
    "LTsiXi+64x00qyCZPTPA02df6b5HfV9Aw4wgqZI9XQDwgcDvXI7ahhgaUUztHFMge6kRDL"
    "4QgPws4ajnLKniohp5OwpqfVEgRVc2fYYpI3a7iU50iyTT/O8ujloPzZ5JDHhGgxs4IcnN"
    "2NLJ44ezohVUPXvlGXM4rINC9gVH6djaVub1bowFn4XtlY4BlYwMAVAMh5di25uyNSn2Nx"
    "JNEyn0imJ6C/6CTb/mf/vX9VhNUsP/X2FajLlU4X0ovKNG9CVBJqgv/KMpdbLcjNikNNrs"
    "6clGsC3Fk8YRXFmcHPDbAcne44+ZhQE1A/wv70jWV6FuG6QDY5Vrh5wPOkch6n4NEprvVD"
    "olPvtpGdrd06JTLPZPooTRYdeDTuKeTfk/g2fJEASpqNpkQAkwO2hAoB5dFqUa4eQ6klqH"
    "wynebR4ZxK41Qap9I4lcapNE6ltTiVxqm0lFATUOdUGhPAV0Wl6bYCrVf9e4GS1Tu5I9ap"
    "DgzN2papVjUNwK9mvCgWgD/bxrrYWcjjO+Clwil0wPlj8qpTTyaR88enqHXOH3P+uA6mHO"
    "ePm8Ef+2Vls1nkdKOz7LKmbhHXY1HK0cNAdza8VxcnatKHO5ej5XPiMpydZoWd5nv76723"
    "n83HVU7sNDhWFRs4zgqgZULZmCtdI1A4+1l7cm8sF/pozeaLW2k8V6bS3xbwwdMTEjfcWg"
    "ALcajcLqbifDAZu0UBojeK0Prlx2A26psCsSJUAN6vvqg80wp7mCymwy89wXuVjUdpCtvO"
    "Zq5qIm9kYzQZzx9QU/9CNoaL0aMyW4x6QnBVRHnlF21A4FvYVYxYVTgq0qSiwp325dXl9c"
    "Wny7CWcHgnq4RwmioyTMV+hQ4nAkpdm1sDMzWI6OKFj4fzeU1A5iT0kQnQJXBxK0iHpaV5"
    "nV52GLA08RnqC2KQeXxdjqQKfFcMx9ta0p+Pg6l/ZPPAPat6JI4X6ARo7xW+d+tvKreSW6"
    "fJK8iUvseGgcZDF2To60li89DFKWo9T+iCH4vXrFJBzYE0o5oNP8ONsrzE/jPcGKhbU1d4"
    "8xSuoSmnUk0sCf7Sm5WpfZvDR3CuuFJa4Cx3jAllDj0hYQU98Y8bcdoASzeXiht54AEkdg"
    "JIMb1gLUwCfZiQO+kgkg8GMDCjdy+EvtRJA+gFJAM/JJHqTvRw4lIkAGvq3ezxZmIuC9Zd"
    "2XEJ16mFAQkg7yQVCqVVQVSGK+BABWQRdHj4a8HDsbThgJNoZPTrSadwEu0Utc5JNM74sI"
    "ZtKYwPE5TEDDhom5Gdl5GItz+jIiRsX7ZyNoJzDqxwDupqBRdyB6jr3ThIqyB7KxyhC74Z"
    "jmZDogtiW4GAtQvhvxPluFPl4LhfW2mbRltZ68bWAZjdMsTcMpI4zy4jAe2tE4WBTopzoJ"
    "NAQ3Cg464ulVdza2Egnq3hgkHEOS19PIQ7l9VCfNG5+hSii95kATsbicMhYZ2GTuhya4W7"
    "5mjwxckfD+GLigdxGQgj4mkDjGX25vw9o5jQx/GQbrMP9A8Avi3VN8WESPlLKi3OhC4KwV"
    "yEAP10XoMBHYCkrUwbHAh0so+jId1uX9YEahQGOXBIY7o4GtDV78ooE+hDxzSuDw41D5M0"
    "mjDnYZJT1Hr9wiQsVJ4oI0hCw+PvD6hQH9F2UDiFBR2UH0wpoX70wlC/q7qL26ObvLWnoD"
    "Sh/dn+CtPKdieqeIlix8jX3OUYu7lVNlrQebImM4ETC2wA7uGcbwffTvqIVZAn4z51FWQk"
    "0xPQX9m4FQdoB777Iht/SNJn9NZ7beV7dFdcD3k3UyiNpphgA22m+tpIadMY+oxFVBwR4w"
    "pmWsE+2WUra9X+VpAp2wk3JkJUBpngPXegRePoK/wEIiW3xuVOutQS/F0vpkVVHzsq07z0"
    "4PI32PP0a55+/Y7o15Nh4rziKWo9D6/IN9xXnX7Nd4Q3ZEd4mEgtWo7+HFa7JvKKqZZn+x"
    "lFlJai+kIVUIlfWzawbT+5aGnp34HiHc6y9AjEGM0Ix6OztTmzyA6zGNcYhQmcEmS59mdR"
    "U7jbzWMKd7tkUxh9lkjq8+eihxQW8f2UbqoTltFv/T64lSY9wX2RjflUHM/608HjvCfsrm"
    "VjthiNxOmXnuBfFGF5y6+w6o5w2nMgY0INdBGrmBdraMhnzAlSBnFEqHlAV3LAoDs4bf3/"
    "cKVX9Rci1xkTa1Da1K+dzsXFVef84tN19/Lqqnt9HvKe6Y+yWNCbwT3iQGOKSJOivglUcN"
    "3fSR8xlPcojW8H43vaaJ4vhmpruxey8Tid9FGNbfdmeC0b/cnocSi5RTjDS9m4EwdDdMt7"
    "ZeNpAP+df6isYgHNtKhMJqxw8xatSp4Obsy0EJUUl+Rli9lhjrDR1kI6jspxDbOsYR4IIK"
    "+i9aSEeSDgFLWeJxDgE4OUkYC4FA8FZIcCIuRrKbEAt6iH22XTowLxccZmWOBGXSGliZqG"
    "TpLZHxzAtT/LFyJ48kQV1ZPlZVlOJwbwXV3pcHRb5hr/dMYDH5c66SqmHhTUeW4JsZOG0D"
    "EddVWgVEdKrjEZmKXV6HhFjeiRTYpxYJPAbm1QBNikGAc2nTi8hn0jq4QeXawsh5hv9G66"
    "R855mFPUei4extku0cHKlDxMTOoAB6s+bDrFqVJuaTg6QCMiHM1sUssbeiWQWjOvp7xcFp"
    "vg7qeyYlM1x5FSaCiWSRnOYX8Nxzgye5nmCueWatiqS07l5gtTMmd0nKGzkz9GsQKfokT/"
    "KWKM8qRiZghFvwoi5fMxLsUfkQmD44Bs4VokCUMj9+5OuZ+K43lPiLyRDe+NePvbYhZ+5L"
    "2TjYfJ8LYnoL+yMZWGkjiTeoJ/IRsLL9ds4aWZTaW7xfgWfYxeZWPyuzRF5nVPCK5a+VyF"
    "ipPM1HWwvOXkPHYCxyM6qk/MLI3rUJ8dYCkhMUQDbFqSI0xE+NWHkArcQIjjiiVCj7wznT"
    "lAq0+H50woGf16cmJ5mFDfh6A0UeNSPDcpm8aJ+GllEQ2EBJd6or2Xc4gPNzZpB/gockbA"
    "tmGz/XxDqvFZPqJBg3LK2hM8BsPgvKKVD/2jYBszJxZYIBaezCWmEtIc/CSYmEH7JmyyyX"
    "r4Sn/OY8/dwOD5MBL//CX27B1OxvdB84iB1B9ObrhddIobMrxHShE1xyX5thuWtWyjHVK0"
    "NXliQpyPTfCxrolAGwKOCnH3Idt92BlhZXkPyPycu7023XOIDbQcAWFvqpeA9cIGuetJsb"
    "ku5Ng4ElkW2XXKogN9n0+WmBS5XTJvmB23QP1KtUNf0I37nglfoxkj2M+DhIfUh9y3Y8W3"
    "S6qG0hrFiHOTlGWTlPuXRDU3mHfnxUFL90R4ei9P72UPTZ7ey9N7a4Tx/vTe9FOsNIibzk"
    "bUoADzg7nSl+rbfnc51vAsn6/86snwmgqn4836KleCzftp/wYPfVKu7KIALBzxiIMaUxKA"
    "tujuQfV2WVta44lv3Tx5b11y2luXZ71x77vH9/82T+sYqs399in3653tq6m3uWe/fRVrmN"
    "O+8ncOHf2gXPcsCxRe8L+AF0GL7kkLYw9+lIIff8GWmWaBzUrVoLKKblnDipfI/7Bqr9Fw"
    "aeZG12gMuVCggZZcJVsYlsBRcaXHyImRO4lGYHzs3Ej4NXXLXeKVNq0llZRtoC1VX9sJlx"
    "8ZqqtzgKo7JamaTXq1aZq+OEDTF1zTzGt6C3HHVk3OPu47Ktek/aplHPZ9yufaiI+P08nv"
    "6Kya4AoVG/hN6rtH2gRXstEXx33JPdMmuGoVMCHLLzhggX8ArRgvlBDl6x7L656nLKXIrv"
    "KEYBM2VCWPlc93rnzWwfJplh0tdqtiNHtclE8slieWp6wCEyslyCcW3cR6wuwHzWdyJLpg"
    "GPjWVPrbAo5RaYqMCf9SNkbSeD6Bt7xXv0ySXx8JvvsCW43gW/eVDTuDBx3J0Ncz/MSDjq"
    "eodVLQkSd6VxpICaOMxQorlrGVt5nA8mzvKrfx8mTkapORY8kHx02oZ3Q52AtwckXkKd8n"
    "mPIdO+cwKyUpeSBinpQk/3TBo6ckWY4dJh55h4y73yak14GxtPnGZ6ZykGoYOZn1H6TbRR"
    "C/oCnyHAj2hPBSNgZj5XE6uYcrw6wnRN7IRn8yehxKbhglvJSN8USZPUz+6An+BbuRld2M"
    "TKk3x6n1dnM93/p6ummCI1hTKVUcEeMKZlrBju6sqLaihAKNyK47QgYjzxGtGmFeOvN46a"
    "Ge4a0E6ULkUyyz040yuimUfcSYVkpMPoLuAFwpoLunmN+BhZ6YRTHP7onDjhnnBfOGYqI8"
    "vYFl++fFNF9WQLE3qgYU2m25WOFSnirvujcm4Tl2u3lcx26X7Duiz/7Cwb4GwFG2FmZ/x1"
    "7Qo6JNeJAfD3T4j5+BBdDpdv5juOC4J3fEFZJLIarmbNWV4hIihR412A74A4flB46vMlRo"
    "9QCNR8W5vlnWNy5SUYQMx/VTxw0FEM+pS3r7F7IBP0Hv3RfZuBsMJeVeGktT0W0Wfw8/Fw"
    "cuGe69skGFx3RTcCkn9cFndz1md9EFHd8D1zrLWufJvuSltp5pnzzZ9xS1zpN93zPZ973O"
    "UC+QlsMkpBmJqTyj710z+lJDPa2JiQHmJvxDmyKcrCFWx7GeN4eVQiGlpk2OTSfHgZ+pxm"
    "dU6ZPweeMc4cBPngvJSi7kUbMUGF2Jj5amwD00oipqaqtzD+0UtZ7HQwseqLQngEaluDtx"
    "WFndlDbKs3iTW1TqqI4cBy9GR+MxLV7HWQFknA4csM5j9Kbb57Z7A1FFh7LH2D60+5d8Ux"
    "A7hjDSvgddCvd8odBYByybx62ZNJsNJuOe4F+k9/ewEcCMzM2NudK1wpVnsB2xraL54lYa"
    "zxW/+gyKS8duyIbYny/EoXK7mIpzV5mJG0VUeJGvcFBG3aBUErzuQUfODiYmBuNEm1QDst"
    "O+vLq8vvh0GSYFh3eyMoPTScEb9U2Bvw3jXeSbHVF5pifFw2QxHX7pCd6rbDxKUyVcyyJv"
    "ZGM0Gc8fUFP/QjaGi9GjMluMekJwxcYah8BH0FJMjKgInxCYCaGuzS3utEMiojsBjicGT0"
    "5bkaGuJ4GRh7bSzFfTog2HxoR4iJls0NLSQglBDm0KWk63VXyI8I62SCFcvLjUjrppejg/"
    "NYdjfFpfnPXFW6mFWYJLgLvvdtR0hGMPn1ITJjh9XE/6mIY6LkgbV8AYRytM7ZaAyPqxNg"
    "3ojv49xSzva8yZZhaY5pRuUvCTTyvGyZZ9YjEbqz0OdMyZxTWs5XU7Fe/mlEPWE+oJ7ots"
    "9IeTmVt7y31lg8kKVnuNknxJyR2PgzmvaAiXTcA4pqOuClDoKTkOLR5aasYwKcaBTZGGK9"
    "MuxhlGBfmOM3ZSnPiOM04Moy54PmPTtJ4nn5GHA0rnrPkmPr7jjCnCLs+OM85PM8NPV0Cd"
    "umd9gPUTsPZTp8m2Z/moU/esjbUrVwl3GjnLw/YO1/CK84dv+F40RonRdzsViNEF5UDzgn"
    "tnRIBraqfn8c78ZY42ESImxafSnlQI/1FyuOFzIsc/xYcXw6ZPPqOH1typxM7ZGd/uQ9DY"
    "IosKExT2fSAeAGbLzvH1lUI+u1p6QrRJ6cpl1EenLRnc3MrA3Tzx3S45vtvlZ0lzc5KT/Q"
    "3UOif7OdlfX0gzvDLORpfORvPzeJmp3leFx2uphoeBZDjWWw7nFydwltMPDmUVeM/Sc1aZ"
    "a8lb7fr8Ev49VzVB3j49XVzDN1dqV/ggfoKX5+dPV+KnX3/5KERbwoba8zW8tbw411D7K3"
    "TrVw0KPHXAJWrbaaMP2m3tg40K+8Eh+wu6fdU5R21Qy+X5J+1jKzEqmPhCWEJAtRz9GWF5"
    "hpIqvR54tINZFiBUUQr2jFTZnUiTXP/Skg7tDVC/AYv66KCkHMtlEAoSApWcceked0ULdk"
    "yII53zvFbwE2Pakut0Bu0bgW+WZ11Fnc7i56WUfkpKnVTBNsmR5raKHo7Cj0Spi4YDk5iS"
    "dkmIceIlm3iJOh6lcAPwF4h+n02nCRJDDV8T4H14AnG71J2h+ULkBeINzrJ4ABU1VVbmyz"
    "EKbDroPGnHG1rul3DfegBHYlFuViD8FqalbG0vnhr9lHvKrHjKqvtTaFyMnUQj7N9j+Bfx"
    "OZMX6IRYA9EuP5AeW49yJ7pGhQ5YTepjbFLE1p7AMzQ00nD+NpuM8XDuJJIGvK45wr+FlW"
    "7n4dPqgyaCIttPTrrECdhRB0k/WX12cClMZNhDAY56cdT1Dc0K7bVuXoLTZZ6Tzy/JB59f"
    "ps495wlORYZ4/TiB0OKnZQWSgvwxnE0LxFyrA4mBhQ1ypwywCe5+KiA5vmJkAPwWwngxHL"
    "4bGwAsXXtt4WgA75OzTP9/14aZc+WIYVbs7MYEWH0lHuarMx9dJfvl34GFr4pItkYiIg30"
    "FTvdPEYJbEUuq9VNmSVoUlEg7DdvILqV8B7wPzrYrVxkJyYicpAbwxrax/BjUubCMR9mf/"
    "0/HBILvQ=="
)
