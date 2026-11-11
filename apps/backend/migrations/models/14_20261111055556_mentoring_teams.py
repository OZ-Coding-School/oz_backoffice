from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "mentoring_team_members" (
    "id" UUID NOT NULL PRIMARY KEY,
    "team_id" UUID NOT NULL,
    "period_type" VARCHAR(30) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL,
    "student_id" UUID NOT NULL REFERENCES "students" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_mentoring_t_team_id_84acd4" UNIQUE ("team_id", "student_id"),
    CONSTRAINT "uid_mentoring_t_student_e1ec95" UNIQUE ("student_id", "period_type")
);
COMMENT ON COLUMN "mentoring_team_members"."period_type" IS 'PROJECT_MENTORING: PROJECT_MENTORING\nREGULAR_MENTORING: REGULAR_MENTORING';
        CREATE TABLE IF NOT EXISTS "mentoring_teams" (
    "id" UUID NOT NULL PRIMARY KEY,
    "team_number" SMALLINT NOT NULL,
    "period_type" VARCHAR(30) NOT NULL,
    "name" VARCHAR(50),
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "cohort_id" UUID NOT NULL REFERENCES "cohorts" ("id") ON DELETE RESTRICT,
    "mentor_id" UUID NOT NULL REFERENCES "mentors" ("id") ON DELETE RESTRICT,
    CONSTRAINT "uid_mentoring_t_cohort__152ab3" UNIQUE ("cohort_id", "period_type", "team_number")
);
CREATE INDEX IF NOT EXISTS "idx_mentoring_t_mentor__aecc83" ON "mentoring_teams" ("mentor_id");
COMMENT ON COLUMN "mentoring_teams"."period_type" IS 'PROJECT_MENTORING: PROJECT_MENTORING\nREGULAR_MENTORING: REGULAR_MENTORING';
-- raw SQL: 팀 (A39)
ALTER TABLE "mentoring_teams"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_team_period_type"
        CHECK ("period_type" IN ('PROJECT_MENTORING', 'REGULAR_MENTORING')),
    ADD CONSTRAINT "check_team_number" CHECK ("team_number" > 0),
    -- 팀원 복합 FK 대상
    ADD CONSTRAINT "uid_mentoring_teams_id_period" UNIQUE ("id", "period_type");
-- 팀원: 같은 유형 팀에 하나만, 팀과 유형 일치(복합 FK). 팀을 지우면 팀원도 지운다
ALTER TABLE "mentoring_team_members"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ADD CONSTRAINT "fk_team_members_team" FOREIGN KEY ("team_id", "period_type")
        REFERENCES "mentoring_teams" ("id", "period_type") ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS "idx_team_members_team" ON "mentoring_team_members" ("team_id");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "mentoring_team_members";
        DROP TABLE IF EXISTS "mentoring_teams";"""


MODELS_STATE = (
    "eJztXW1z2rq2/isMn7pncjuBhDaHuffOOOCmtGDn8rJ3e8oZjwNK4lOwObZpm7PP/u9X8r"
    "stydjGJrLRl2CMlgLPkqW1nrW09Gd7a6zBxno7AdsHYM60J32/m6Bb7X7rz7aubgG8oDe6"
    "aLXV3S5sgm7Y6sPGlXKaK5bT3vlIfbBsU13Z8NNHdWMBeGsNrJWp7WzN0OFdfb/ZoJvGCj"
    "bU9Kfw1l7X/rUHim08AfsZmPCDb/+AtzV9DX4BC7391t5b8AN4c2UC1QZrRbXbsM23tmWr"
    "9t4ifWIC2KmF7qyMZ8OEd1Gnu+/KowY26xgG2hp14NxX7Jedc2+xGA0/OC3Rl36AnWz2Wz"
    "1svXuxnw09aL7fa+u3SAZ99gR0YKIvEwED/VYPPf+W+7vhDdvcg+AHr8Mba/Co7jcI0vZ/"
    "P+71FUKyBZXy1npWTbB+q62ttzr4qWjr//W+ZURCUSR5rszEuaK0cyhjZehIkZpuI+T//M"
    "vtN8TGudtG/2DwUZi+uXr3m4OGYdlPpvOhg1z7L0dQtVVX1NFiCLg7blzwMOQH8MeJ+n7r"
    "oD+C30bVVwDTQqKLhDrgTyiiCP9GqIlwLPvA+tBlB7s9my+GojTvt7yLpT6Bf+Vpv+W+tj"
    "Opor1VfykboD/Zz/Bt9zJFNb8LU0c73UtHOwZ8MN3nVvI+6TofISWFStG11XfnmqgR8rMQ"
    "lSmkAm+kV6yBzMM9jvFVFoyv6BhfYRivNWu3UV8U9F7ZmeARmMAb3UUegpTuGNZGWxImYr"
    "+F/i51aTT47L33roo8DZ0smurQNdXBNLVV7dWzAqc09IsKqifZB8s6mQjzwUdxCKck9wJq"
    "Rlaca6gZ72qpC5Pb0d1CXsz6reCSjdkrNAQKrSaB9OkWkva9KA1H0l3OpdsX67e8C6iV+/"
    "up/DtSnn+11KfiJ3EwR/f8Kzb0ZIIfGvjp2mmYsoYQYlvbAvJikxBNaGrtyb71L5h5tsow"
    "tuajiTibC5N71P3Wsv61cfAS5iL6pOvcfUncffMuoZegk9Yfo/nHFnrb+rssiUkLLmg3/3"
    "sbfSd1bxuKbvxU1HUUE/+2fyuh53+ClQ0nP9WCIOQwKTBBhmfNwnZFNsMizbLAHqyI/5Pz"
    "uYpLlvBYnciuzo4+/IFrWd+8eAOjJs+ZN4ZTH7P9bl1Q63FJrnVWtE6YXb1vH51c49yGko"
    "/BoIgfQWkwNt0ew1pEni0LmDmRjYiUSRDVFk5EuT1+J3JAPqMXh/aDYQLtSf8MXjCDPQGo"
    "R1wuYDcBYVlPXMO74ZNkqj8DojI6qiAA8LcC24FgCueR6Wgwb6dODiWAPHA6ygozm5PBQZ"
    "QpsyIFcTSyH9TV95+quVZiQxx9YnSNxJ2gLf7RtrtN3lF19clBCv0k9AM8RcjC3n4WVitj"
    "r9tULh9vdJHG5RtwpXlWVLd9BVz+t/bONH5oa/dxd/+bfwdh7LD1/mwQNP1HIgTAyXtWyP"
    "uoNotwLVF5pmn7z8JnQe63nJelfifLd2Ox33Jfl7ok/C5OEYsJX9igVvBHi6gh8oNBFGZZ"
    "PQV9726vlwX3Xo8OPPqM+97N9sK4732OWs/ie3OvkHuFTPgrNK9wIMwGwlB8LRclhJ7gms"
    "T0QndJ0E+rPquIuxSsuBRgq2qbPNZqIFCOhXoY8Hrbp8+q9QzNjZ1qWT8NM5dfQBBtXkCu"
    "EtBz51Idk0fF2iIWx7eXxdft0X3dHubr7iBEQNH3KA01D8hJuVLGMkPTR6eTJRGqQ0+E6i"
    "SRftBM+1lBvgjZyyHjHJdK83DqN3ekIIwclAR+cH02jR/qRjkuQ4nQDU9VqpZPcyEv5OAn"
    "RHmqEjsOPc7jOMak8gOYGvw5RbRN7IDrnGWdu3bAETondsB1zrLONUtRoc/8g2DI3BrGBq"
    "g6xcGPyiVU/AAFq1p1gzun1eutLI9jKr0dzROL5mJyK0Iz0tElbKS5xNNImidW0I1q2crG"
    "eNL0Ak8YJsyfLpafLpeALDKVxiW5llnWMo90UtVc05gXj3Seo9ZpkU4sNEcPIkWCO9hu8I"
    "R15cl/+DwFG9VBGB8MaRvRazYmaBE8QrZONO2uOGjEjL+mgFZlsPIemFvNsuBXpYYsk00u"
    "0gKXu6AxD1+eT/hyBQdCniCE375xwctOpo1tnZSNbR18Y1v0m2Egz8Evm+ZVxMSaELRMsy"
    "3EL/OYWeFD+mYifPktZlqMZenObx5RwWAs35JycyrLIonsWDA2gLACTlT9ZW6gvxmzfqaw"
    "n8LL36s+Rik5P85vUxKLUuyXmsg+gDZ2wG3GF6FHw3T08R28+GB7aUOBqryPQkGvgf1sGv"
    "un50As0TMx7QjeV6LYB2s4dREOfwxh+Y39UvrCGwwhvuTyJfecltzyUyt43kqF4HJj5pTG"
    "DGcusw36enJYNOayEIflZFNTDNE8VAzKcD7KDmXjsSydhomE3hPm6XE2P4GeqdVqntfyJ/"
    "zepP0fjuK45Y+Z90n7P+IalGH5h09j6maBVPMfe5zSNw0op/EDvrWtlbED7liEH7nv0F5m"
    "7iGw4iHENVQk5TLeA8vmbfsO2jvCuN9yX5f6rSzPB3Dh7Lf8q6U+kD/K03m/5b62C5jDFV"
    "Tt8x+cHM9GVIaXrInjCX7tNPhpkRzGmCRPwmAnLsuTMM7XlYnV9Qmts6xTZUSEbzzm1b3K"
    "hjNlHzcaeTi0ufdxN9GTvkjWnQof0gzVvfgG+RLLpr3ODvlbw7BX6nY3s9XHR6rnS2h1ke"
    "b+Pnjt0Qaxx8dK6niB7W5jvABnWPn/ziEg0MOeLNj1LWzCvWJmvGLyvJzNH/ZlmfaEJ4Ik"
    "3KHCXN7FUhdmsxE0vdD5G8ElG94vt+Pp0DfXjg8m6nyTX0KMG6BJ6sNbnHLCmhDjsKbb9V"
    "ET4EgTVPS6aroZmhhhGWz8qG11JMi+Fdl0kBOzI1P2vls9Od3ax9qk2vpegeLTWPphFWmK"
    "nc/P1+NWPrfyuZXPrfyo1osczFHWcRys6Zlb+IzByi3817XwX+lkjroCzO6BHEOwU017C1"
    "KO40g2SbXs10FjvpvlfOx1qHOo8ZzrWkyIJ0LxTSwn82hSN7HQMS5jEwvbUPcy7X/upex/"
    "7uH7n809cVMCfbNQIMC3CfFtQtxb5wWOzlHrhETa4gWOfAfvyL1hTfWHKy3REweN4F9hqN"
    "K9q5geuW91Fr6Vq3PkUR+1GYjQDcsGbHsq3i3GwhTVVHcu0P4faT4VBs4OIPdqqY+kuTiV"
    "+i33danfC9O5gmZW5ZN822/F3i71D1NRHAvSAAVewuulPhRG46/9lvPCYy6MT+I1Xc+5FX"
    "eOWqdZcXE2wqdMcxJomCAPDSVP2TEszQ73i2dmJuNiHFZmtx6xUPqg3PBl+FCXEF0jhG7q"
    "OWAPRtiwuTBDENN/zEuMFN97XTYd7sQMmTukScgmD5MBixMU5D1HDdEBKT2nDNBIqZtNgQ"
    "wndg7tRJR1MDfgn1PsQ2Rh9Sp7F2IpXFl8Gk3hzLD59jB3pvhzFyfRzodEe91wOkPlNsun"
    "qnamZpia/YLDO9uqm81Ip0R5o3IJmDXX+K3ZIgS/L3z5r6vu+3c38FPnO6I371MQn02E8R"
    "g/d4rTf3SU60kEcfrvHLXOg7gNC+JOwZOG/i360oKFDgxKTZ3NIpbNaDUjPShq0AW3Yc/H"
    "huWb4vimuDpM0DVdq2tR+qI+ya05wkmvutWwkYjGrIWcJRdxUR7/PFArMAJZibGkqNHYNG"
    "P9IllDEB91xBLtrJQZYXPWKKnKCAMbPWuKL7v7POmTSka3taizeorDDPxIXsS0hm2+QfdG"
    "tfdW8hPu0bLi0fLU5jNMbQ4fyiK6DqVPp+L2vSgNR9JdzofLF4O6ci+WunB/P5V/F4f9ln"
    "+11KfiJ3EwR/f8Kzb0ZIIfGvhZiOJIiPLDGNgJP+Cchgn+CVY2XLNVK992aEywCdt140/V"
    "Vab90Fcp+6Gv8P3QnDqko99c6pAHd5umdb63g+/taB6s7OztqC2cKVQxP/2kxLxj8kRbAr"
    "x82wzfNsP4tplECtDx6WAHUpQaopBKk8TiQaSUI5FynIZ0Cvr8Gf5wHdgKP++IPYqcb1wI"
    "StNlYGJ6aYXpMB4GPnV5oPXbNw7a8rljzVLgdKX9IOAL58ANUHXKhBGVS+AMZ6fKViIf+9"
    "NOC7eyPI7xGLejZIG/xeRWnL7pONDDRpprKuAbRlTNdJYOxYtA70zwqP3KM7rpPZRC6zI0"
    "3CuYSTij2zBujzO656j1LIxu0ljOyZVRxDlvls6bYS4KBnlu7uGjuZaAfS7ni1HG3REMhG"
    "snlFJ7omngV8oyRCGjHsSW+Qy2Sk5fiz6lnjmp77cP8GP88DV/YPJD2F5jyr1IoR7imsOw"
    "T9/djwnzLf5YGhzEB9l4ZOuRDGtcKs1yrCG6KSAiyy95mpa+zg1fVOaswatjEuZYkCQvOT"
    "JPEqYr1m95F0tdlu5kJy3Tu1jqojRELZwXlHgrDOaj30WUeuteLXXk+4/cxE3vqp1twqj6"
    "JBPNWhlwBX3aa7BD0hKZcpwJQbZpXM9VN0v+XpeevtdNIh7wZCZw0MuHOVmao34Idc6w0a"
    "GvJ9fCGbZz1HoWhu3VN9mzputyEvvijnZB2pIf8FuAtCxtD22csmwmd3ZBIS6zbK1lZHN4"
    "XaEujxu27P36+NS0mdtL02CvlB2mTxEErjh1PqEzx1gsoUIqmRT4SaeUOYHMCWRm54QSCW"
    "SnV6UYjUySPZIPZWwfZz461MWjCKOMS54zjhbYPCo79UVRt8aetBWD+rgTJAs98IzB5z3v"
    "3c71++ubq3fXwUMf3El78nlh6OYzIpwHO0et80wz1kkbnmnGM83YB/+EXEJGFqEAf8CLmJ"
    "8PJ/C6+9le21iJRck7mYoLdVKKC3Xw4kL+s5UvLSEu1bR0hEqAdh1/ByMi0IezqOI9MFw8"
    "q/15OO+34J+l/nk4QFeDdiE1ZNJCihKSOtBXVkex8s0noQjDiBce6BUg3M2PcJcjnAfhq/"
    "wIX3GEMyP8E4DviKClgXx4po73cMKc1z9E8fNQ+JrTxHPERGnYb3kXS93ryL0DL5b6x6+3"
    "0xFs4r6yMZ+v1RdF156e7SN0lezjhNoqoClHJ44+pNHdR7jKOi9sasc2bHWjuFbLIyAoiE"
    "ruEyQ5uU+L6D2iI2qBqTwbe0LQlI4xUZjDTIA5MhoRTgRiKT00TeygQUiXEp2OYASn5KMw"
    "9uU5xDwW2OioEI8FnqPWabFALEiVJVYS49SLR0uaGqxKFAArIa50DjnZlUaZpvBJAebsRV"
    "9N9/QjiQitLtJiTKbTXrGggGLuT3IKkZNOFzl9KEz7j37CQ1GshKLg/3x6IiWmZqXvA3GW"
    "g1Pt2eCjOFyM0d7l4HKpTwRpIYydo3bhaxGCoYKTgVbGDhwVUon3wLRaoEnfb8E/S/1Wlu"
    "cDaB30W/4VOhDqozx1joNCr4yop341A6YLSSpwcJMn1m95F0t9thgMRNGpEhBcLvUPwsh5"
    "rtxXZrRkFvMP4pIN9A/q6w/gbuCjpmvWcyE9J0T56VxM6xnYK6SrVc58ekzudNtnLitSa9"
    "k88H5nAWfCy4stLsjBTYJrgq3xowC2mByHFhu3+ha6X0XGLSbIwaWC6xboIZi7n2aydADf"
    "iGxyddVWdus/rY1mVYZ0xEt/2GsbW9Ott+j/vYZ3jrCKrbS+5fpmInxJGrWDsXybXEJRB7"
    "fJwm+maZjKFliW+kTwFOfgF2X8Y4JNyJ5JM3bEL/N09ANbZyxLd37zpEri6L96dZb64J+j"
    "OEuhoixlFWNpDKIp23pesRwIm/CWVA0EH8QlIJwvilJTfLMUtKFH/KqMyMTqrhBiMcm6LP"
    "QoTLQOzMHoS3u5X3U7N8u9uur0Wsv9w/VjB/696a1b/9MSvMKJ6L5604N/u+AGvbm5hBKr"
    "x941ElivWm/WYKVZsEerJXQuf3vbQv1dXsI2729Qr6ubS9h01Vtfoj7+dt1C5wy6bVrSYj"
    "x+m6TxGPpaxAop/pGS0QLasbhULA6FOFgnOhVsrIHPH4jVUuHRKRaiU7zO6GH2vPw6o3x7"
    "WoXHJMWmmhwgJ+Wa4LYlkrU7WZK1O/Rk7U4Sa7BVtU0ekAOB5qHb7fWyRNl6PXqYDX1G3m"
    "h5XFQU74XlmQRapnej2VycoqBneL3U51Nh5EZM/SsUwp7cj8U5ahpcRu4qN5fKvTgdiNI8"
    "0iByN9pWkIaKCN/IX2Pdxe4vdVGYjr9G2sXfL3UUrRlOhT9Q3kN4vdSHU/n+HvYmL+BXib"
    "xZ6mNRQHXgnRfY/5d7cewEfP2rpb6QPkvyH1K/5V0UCQJfZZlpr+gz7RUeBDb25gr4dgU2"
    "NukUJiZ4FH/J2KxwaqISJZ8Vi8RHBXl8luX4rGYpfsgKVdRzHh9c3YcOPSV2ccLzT4M7tT"
    "0AtYbJSaI0lcfj/Cea+HLowBL3irbYemtZsKgdXiLh8i3NPohTZ4WPvCmyrJWf2wR009hs"
    "UqZUimkbFzvrg38A/JL58VuXBV59ViLKiVMmUC13O0Bmxyom1UDvKlN1lW5KdZUuXl2F72"
    "2jo1/PXU58b9s5ap22t42Z2Ddrei4nnQDFhHICGhHhqQSpqQR+wO3IIPcCdtPwEHdkTLGb"
    "PsDoDFDj/IGBoTuR/g/aBqScU51sdJF+WrXbHH6HDeAFQ88nDo70reQNy8aEWI6oFI0XVl"
    "HR0gEN/CLMwAeA9mQaiXPZRbQcwCzt3ySSWHuib+eJijXpJJy/dbtXV++7l1fvbnrX79/3"
    "bi6DDH78o7RU/tvRHWKFY4og0cTw0yegfAcveYZ5Qqyckc5QIk3nsnudaaR3r1PGOvqQ0z"
    "jNduiz0DiuJVpE63FJHvlkh7VxtZyjJFEuByPqBLp2PmF59ERlHcwN+OdwaR5xvV+pcOb2"
    "XY2Gedt/5XTLyHAQXDMqbnT3DHgiiq+/UxTc8f8X/Le+rR+55WQNurnOW6DDO+61hlDcr5"
    "z33MtjxcsLxs8x1V+wTlj2SNoTUZrL037LfV3qI2k2ny4Gzr3wul3Amis/8E540rKazgRR"
    "ltXCTLJ0BLfcubwk2QYGnqtI68UWkGKwB7INHOvlJ6vbmr3JhXQg0ER4q+D2ih0TXOoBwa"
    "yhnj/3Jy98JZ4KXG/wapicOZwKH+Y5bWhXCGVbwpelLgzmI7R7wH1d6qI0dJM2ndpxc3E6"
    "GUmCk7IZXjNi7nHa7gxpO5591TStZ8m+CvmQnAlDmCBPG4rPoi4Rh1yw3cZ4ASAnvhRxnu"
    "uWhNkh9/KCGxXiA5fsAzu5NrnzMnHZEvF91ZhpJdmEycccBzt3/pvoddX0DDjKDJkh1dAL"
    "CBwP9cTpqGGBJQzn6GSZAd1IiOV4hEdBZw1HGbOnSsjppMzpuFr8oGrmDFtC8mYNp/IMSb"
    "b4cpZFL0flzyaHPCFES3gq6MHZcGTxxNnzCanq2up77nJGEZnmBYzKr7Ox1qzdBh04C98r"
    "OxM8AhPopAIAGc+upXd3QupTEiZiXuYTyfRb6C86yXbw2XvvXRVhNctPvX0G6nqj5QvpRW"
    "Wa90BUEmqC/8o01vuVn5sVh5penTkp1wS403jCKoozg187YNpavuPkY0JNQP0E+9N3puFa"
    "hNsC2eRE4eYBz5PKeZyCR6e41o+JTr3aRna2duuUyDzT6SOcLDryaNxzyL+n8W3kIgE5ab"
    "Y8JQKYHLAlVAgoj1aLcvUESi1B5dPpNJcO51Qap9I4lcapNE6lcSqtzak0TqVhQk1AnVNp"
    "TABfFZWmWQq0XrUfBUpWh3InrFPtG5q1LVOtrlYAfjX9STEB/NkW0cVOQ57cAS8VnkMHnD"
    "+mzzr1ZBI5f3yOWuf8MeeP62DKcf64GfyxV1Y2nUXGG12klzV1irieilKOHgYa2vBuXZyo"
    "SR/sXI6Wz4nLcHaaFXZ6B0zNWAdFb4qwpYkuWK6q0L6fyp/EwVxx6+Y4h85ht5b6VLxbjI"
    "VptBV2qwiXWsFZbbw0Q61LM7BpbWTEbgWnGsUCtr0BaJZXdsZGW1EYuMPTCL03pmeU2Xwx"
    "hHOCMhX/bwHthn4rccMp5bAQxspwMRXmI1lyajpEb7Axk+zUFwViRSngnGEViMgzrbCP8m"
    "I6/tpvua9L/V6cwrazmaOayJulPpGl+UfU1LtY6uPF5F6ZLSb9ln9VRHnl19xA4JvEWYxa"
    "FDoq0qSa0N3O9fvrm6t310Ep6OBOWgVonOnTDcV6Nn4qCCh1a+x1wqNBRZcsfDqcL2sCMo"
    "8hnJi/XgMHt4JsJi7NyyyzQ2DivHWgL4hB6umDGXJiyF0xHC5ti1/uR1PvxO2Rc9T4RJAW"
    "6ABv9xW+d7w5ZSg6Zbbcelr4PTYMNB55okNfzxgEjzydo9azRJ74qYbNqvTUHEhTihHxI/"
    "hyVgc5fAQfA2WH6gpvlrpDearhVBMKhL/0dmOsvs/hEpwpLIgLXGQOEaLErwckrKAV/7QB"
    "Qy9I5EQeePyPufifqxeihUmhDxNyZx1E8sAAOmH0HoTQkzprAN2ApO+HJHYqUD2cuBQNwJ"
    "p6Nwe8mZjLQnRXQi7hBpsYkADyTrBQaF4VRGW4Ao5UQBpBR4a/FjwcS/tFOIlGR7+edAon"
    "0c5R65xE44wPa9iWwvgwQUnMgI12iVlZGYl4+4tchITlyVbORnDOgRXOQd1s4ERuA3Ubjg"
    "NcBek7GSld8L2MefaTOiB2FAhYpxD+oSjHPVcOjvO1lY6hd5Stpu9tQNjsRM0to4nz7DIa"
    "0O48URjopDgHOgk0BAc67upaeTb2JgHi2RZOGFSccenTIdy9rhbiq+77dwG66E0asLOJMB"
    "5T5mnohK73ZrDpMQ++JPnTIXxV8SAuA2FEPO2Avk6vrXBgFFP6OB3SHfaB/gnA97X6ohgQ"
    "KW9KzYszpYtCMBchQN9d1mBA+yCtNoYFjgQ62cfJkO50rmsCNQqDHDmkCV2cDOjqd2WUCf"
    "SxY5rUB4eah0kaTZjzMMk5ar1+YRIWCoeUESTJw+MfDqjkPmHvqHAKCzooP5hSQvnvha7+"
    "UDUHt3sneetAPXBK+4vDBcKVfSiquIlip8jXDHOMndwqC03oPFmTmcCJCXaAtDhn28EXSp"
    "+wiLUsDXIXsUYy/Rb6u9SHwgjtwHdelvofovgZvXVf29mW7orLWYdPSk6jKSbYQJupvjYS"
    "bhpDn7GIiiNiXMFMK9gjuyxlq1rfCzJloXBjIkRlkAnuugMtGlvbkB8gWnJrXO6sSy3B3/"
    "VkmLnKm0dlmpceXP4Ge55+zdOvXxH9ejJMnFc8R61n4RX5hvuq06/5jvCG7AgPEqk/GhsN"
    "OhIHaMVkw4vDfCJKSnl2ZXim9fkQhp7Kc1e4TcqVvTmZhQhDRs8r99GNxxzbyNrUGncJel"
    "k8gh7dIehxf6DxliH3B85R6zR/4KiweAX21Ryo2wnYPoBDJzkT2ma0srw9SUiuAkvrW9vp"
    "3zWNLHu/hv/XPWfDf3MRP5DhH9w2Y9Q2iygyK+oREe4bk2vwOIAQzTV+kAnLB5lwS7BpNk"
    "EWS9BbtHJOg3EpPhOms4QRw+BImnDm9tR0njA+vNgkCh3jNJsJm9d4rcRqxQpB+ousY9LA"
    "lRmay5itGuQj8hREtqxWT18Y8ulZMgnRJh06U0aaDDdga23AnpQnZjpzhNPE3DngNDHXOq"
    "71+m1HY8NlOZIa45k4vBAiUx42P/riTBOdhP1as8fGE5W6iDe4SGMtVNRU2RgnKB35Df5X"
    "E34ashbuWxfhiI3pROLgt0AbOC3XzY1+ymkMVmgMdUUupEX310IJlt3qgi5bJ1Oyfycl2b"
    "+DJ/snnpmsQCfEGoh2+Q5ybD7KHE2OCh0xmzBGRpRjMz+AR2hc4HB+mskSGc5QIulwaiu7"
    "9Z/WRrNqWFQoBU0ERcyp9Efom4nwJTl4B2P5Ngk76uA2Wevw0SYxy3TYAwGOenHUtV2eGd"
    "pt3Tzi8rqXYV6+7lHnZfQRJy7PcPN4aPHnXIIxQb4Mp/IscdfqSDJgYYHMVACb4B5kArDx"
    "FWMD4LdoSYvx+NXYAGBqq+c2iQZwP7lI9f/DNsxsZqLGvolPNyHk7SmR2b0z5RQOp/vlP4"
    "Bp5XTMIyIN9BW7vSxGCWxF34bfw8wS9FDlQNhr3kB0K+E94H+0iQl3dCcmInKUG8Ma2qfw"
    "Y151j8lf/w9+Q8jI"
)
