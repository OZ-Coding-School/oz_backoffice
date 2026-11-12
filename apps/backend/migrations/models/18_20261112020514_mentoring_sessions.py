from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "mentoring_sessions" (
    "id" UUID NOT NULL PRIMARY KEY,
    "status" VARCHAR(20) NOT NULL,
    "starts_at" TIMESTAMPTZ NOT NULL,
    "ends_at" TIMESTAMPTZ NOT NULL,
    "title" VARCHAR(100) NOT NULL,
    "topic" VARCHAR(100) NOT NULL,
    "body" TEXT,
    "record_duration_minutes" SMALLINT,
    "recorded_at" TIMESTAMPTZ,
    "google_space_name" VARCHAR(255) UNIQUE,
    "google_meet_url" VARCHAR(255),
    "google_conference_record_name" VARCHAR(255),
    "actual_started_at" TIMESTAMPTZ,
    "actual_ended_at" TIMESTAMPTZ,
    "recording_status" VARCHAR(20) NOT NULL,
    "recording_started_at" TIMESTAMPTZ,
    "recording_ended_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "mentor_id" UUID NOT NULL REFERENCES "mentors" ("id") ON DELETE RESTRICT,
    "request_id" UUID NOT NULL UNIQUE REFERENCES "mentoring_requests" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_mentoring_s_mentor__526209" ON "mentoring_sessions" ("mentor_id", "starts_at");
CREATE INDEX IF NOT EXISTS "idx_mentoring_s_recordi_07e20d" ON "mentoring_sessions" ("recording_status", "ends_at");
COMMENT ON COLUMN "mentoring_sessions"."status" IS 'SCHEDULED: SCHEDULED\nIN_PROGRESS: IN_PROGRESS\nCOMPLETED: COMPLETED\nNO_SHOW: NO_SHOW\nCANCELED: CANCELED';
COMMENT ON COLUMN "mentoring_sessions"."recording_status" IS 'PENDING: PENDING\nSTARTED: STARTED\nENDED: ENDED\nFILE_GENERATED: FILE_GENERATED\nFAILED: FAILED';
-- raw SQL: 멘토링 세션 (A42·A43)
ALTER TABLE "mentoring_sessions"
    ALTER COLUMN "status" SET DEFAULT 'SCHEDULED',
    ALTER COLUMN "recording_status" SET DEFAULT 'PENDING',
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ALTER COLUMN "updated_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_session_status"
        CHECK ("status" IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'NO_SHOW', 'CANCELED')),
    ADD CONSTRAINT "check_session_recording_status"
        CHECK ("recording_status" IN ('PENDING', 'STARTED', 'ENDED', 'FILE_GENERATED', 'FAILED')),
    ADD CONSTRAINT "check_session_range" CHECK ("starts_at" < "ends_at"),
    -- 멘토 일정 겹침 방지: 취소되지 않은 세션끼리 같은 멘토의 시간이 겹치면 안 된다
    ADD CONSTRAINT "excl_session_mentor_overlap" EXCLUDE USING gist (
        "mentor_id" WITH =,
        tstzrange("starts_at", "ends_at") WITH &&
    ) WHERE ("status" <> 'CANCELED');"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "mentoring_sessions";"""


MODELS_STATE = (
    "eJztXWtz2sqW/SsUn3KqPCmDTeJLzUyVDIpNgoWHxzk5N0ypZGjbugGJK4kknnvPf5/u1g"
    "M9uoVaSNAS/cUIod2GtaXuvdd+9L+aa3MJVvb7B7B+AtZEfzG2mwd0qtlt/KtpaGsAD+gX"
    "XTSa2mazuwSdcLSnlSuFL1dtfD3+SHuyHUtbOPDTZ21lA3hqCeyFpW8c3TTgWWO7WqGT5g"
    "JeqBsvu1NbQ//nFqiO+QKcV2DBD779LzytG0vwC9jo7bfm1oYfwJMLC2gOWKqa04TXfGva"
    "juZsbdInFoCD2ujMwnw1LXgWDbr5rj7rYLWMYKAv0QD4vOq8bfC52WzQ/4SvRF/6CQ6y2q"
    "6N3dWbN+fVNILLt1t9+R7JoM9egAEs9GVCYKDf6qHnn3J/NzzhWFsQ/ODl7sQSPGvbFYK0"
    "+Z/PW2OBkGxApby3XzULLN/rS/u9AX6q+vK/vW8ZklBVZTRVJ/JUVZsMyliYBlKkbjgI+X"
    "/95Y67wwafbaJ/0LuXxu+uPvyG0TBt58XCH2Lkmn9hQc3RXFGsxR3g7n3jgpdAvgd/nGxs"
    "1xj9Afw2mrEACS3EhoipA/6EPIrwT+w0sbuXfWB96LKD3ZxMZ31ZmXYb3sHceIB/R+Nuw3"
    "1tZlJFc639UlfAeHFe4dv2ZYpqfpfGWDvtS6wdEz6Y7nOreJ+08UdISTulGPriOz4maoT8"
    "LIRlcqnAu9NL1kDm2z2K8VUWjK/oGF8lMF7q9malvanovbqxwDOwgHd353kIUobjWBtNRX"
    "qQuw30d24og94X7713lOdpaGXRVIuuqVZCU2vNWbyqcEpDvyineuJj8KyTB2nau5f7cEpy"
    "D6BmRio+hprxjuaG9HA7uJuNZpNuIzjkY/baGQK5VpNA+ngLSfNRVvoD5Y5x6fbFug3vAG"
    "rl8XE8+h0pzz+aG2P5s9ybonP+ER96ssAPHfx07bSEsvoQYkdfA/JiExONaWrpyb73D7h5"
    "toowtqaDB3kylR4e0fBr2/7nCuMlTWX0SRuffYudffchppdgkMYfg+l9A71t/H2kyHELLr"
    "hu+vcm+k7a1jFVw/ypasswJv5p/1RMz/8ACwdOfpoNQWAwKRKCHM+aue2KbIZFmmWReLBC"
    "/g/jcxWVLOCxOpJdnR19+AOXI2P15t0YFXnOvHs49THbbpY5tR6VFFrnReuE2dX79uHJNc"
    "ptqGwMBkX8AEqDs+n2ENYi9GzZwGJENiRSJEFUWTgR5fb8ncgB+YxeFNpPpgX0F+MLeEsY"
    "7DFAPeJyBocJCMtq4ro7u3uSLO1nQFSG7yoIAPytwMEQjOE8Mh70ps3UyaEAkHt4oKww8z"
    "kZ7EWZMitSEEd39pO2+P5Ts5Zq5BZHn5htM3YmuDb50bq9jp/RDO0FI4V+EvoBniJG0tZ5"
    "lRYLc2s4VC4/edFFGpdvwpXmVdXc60vg8r81N5b5Q1+6j7v73/wzCGPM1vuzQXDp/8ZCAI"
    "K854W8D2szD9cSlueatv8ifZFG3QZ+mRt3o9HdUO423Ne5oUi/y2PEYsIXPqiV5KNF1BD5"
    "wSAK86yenL53u9PJgnunQwcefSZ873p7YcL3PketZ/G9hVcovEIu/BWaV9iTJj2pL5/KRd"
    "lBT3BNInqhuyTop5WfVSRcCl5cCrDW9BWLtRoIFGOh7ge82vbpq2a/QnNjo9n2T9Ni8gsI"
    "ovULyJUCOnMu1SF5VLwtYlF8O1l83Q7d1+0kfN0NhAioxhalobKAHJcr5F7maPpotbIkQr"
    "XoiVCtONJPuuW8qsgXIXs5ZJyjUmkeTvXmjhSEkYMSww+uz5b5Q1uph2UoEYYRqUrl8mku"
    "5Lkc/JioSFXix6FP8jjYmFR/AEuHPyePtokDCJ3zrHPXDjhA58QBhM551rluqxr0mX8QDJ"
    "lb01wBzaA4+GG5mIqfoGBZq25w5rh6vR2NhhGV3g6msUVz9nArQzMS6xJepLvE00CZxlbQ"
    "lWY76sp80Y0cT1hCWDxdPD9dLgGZZyqNSgot86xlEemkqrmiMS8R6TxHrdMinYnQHD2IFA"
    "ruJKrBY9aVJ//pyxisNIxw8mZIK0Sv2D1Bi+ARsnXCaXf5QSNm/NUFtDKDlY/AWuu2Db8q"
    "NWQZv+QiLXC5CS4W4cvzCV8u4I3AEoTwr69d8LKVqbCtlVLY1koWtoW/WQLkKfjl0LyKiF"
    "gdgpZptoX8dRoxK3xI3z1IX3+LmBbDkXLnXx5SQW84uiXl5pSWRRKqWDBXgLACPmjG29RE"
    "fzNm/YzhOLmXv5M+Rik5P/i3qbFFKfJLLWQfQBs74Daji9CzaWF9fAdvPthe2lCgKu+jna"
    "B3gfNqmduX10AsNjIx7QieV8PYB2s4dRHe/RjC8hv5pfSFN7iFxJIrltxzWnKLT60QeSsl"
    "giuMmWMaM4K5zHbTV5PDojGXuTgsnE1NMURZqBiU4XyQHcrHY1k4DRMKvcfM08NsfgI9U6"
    "nVnNXyJ/zeuP2/u4ujln/CvI/b/yHXoAjLf/c0phYLpJr/iccpvWhAPY4f8K1pL8wNcO9F"
    "+JH7DtUyCw+BFw8hqqE8KZfREXg2b5t30N6Rht2G+zo3bkejaQ8unN2GfzQ3eqP70Xjabb"
    "ivzRzmcAld+/wHh+HZCMuIljVRPMGvjQ4/zZPDGJEUSRj8xGVFEsb5ujKRvj476yzrVBkS"
    "EYXHortX0XCm1HGjOy8JLXMddx096Yt436ndQ5qhu5cokC+wbdppKuRvTdNZaOvNxNGen6"
    "meL+GqizT398m7HhWIPT+X0scLrDcr8w3g28r/d5iAQA97vGHXt90lwivmxismz8vZ/GFf"
    "lmtP+EFSpDvUmMs7mBvSZDKAphfafyM45MP7FXY8Hfr62vHBRM02+cXEhAEapz68xYkR1p"
    "iYgDXdrg+bAAeaoLI3VN3N0NgdlsHGD9tWB4LsW5F1Bzk2O3Jl77vdk9Ot/cQ1qba+16D4"
    "OJb+ros0xc4X++sJK19Y+cLKF1Z+WOt5NuYoajsO3vQsLHzOYBUW/mkt/BPtzFFVgPndkK"
    "MPNprlrEHKdhzxS1It+2VwsahmOR97HeocapxxXYsIiUQoUcRyNI8mtYiFjnERRSx8Q93J"
    "VP/cSal/7iTrn60tsSiBXiwUCIgyIVEmJLx10eDoHLVOSKTN3+DId/AOrA2rqz9caoueKG"
    "gE/yqBKt27iuhR+FZn4Vu5Okce9UHFQIRheDZgm2P5bjaUxqinOj5A9T/KdCz1cAWQezQ3"
    "BspUHivdhvs6Nx6l8VRFM6v6eXTbbUTezo1PY1keSkoPBV52x3OjLw2Gf3Yb+EXEXDifxC"
    "u6ngsr7hy1TrPiomyET5kyEmgJQREaiu+yY9q6s6sXz8xMRsUErNyWHvHQ+qDY8OXuoS4g"
    "ukYI3VTzht0bYUvMhRmCmP5jXmCk+NEbsu5wx2ZI5pAmIZt8lwyYn6Ag1xzVRAek9JwiQC"
    "OlbtYFsiSxs68ScWSAqQn/HKMOkYfVq+gqxEK4sug0msKZJebb/dyZ6s9dgkQ7HxLttOF0"
    "jtptFk9VbSzdtHTnLQnvZK2tVgODEuUNy8Vg1l3jt2KLEPy+8OU/rtofP9zAT/F3RG8+pi"
    "A+eZCGw+S+U4L+o6NcTSJI0H/nqHURxK1ZEHcMXnT0b9GXlmy0YVBq6mwWsWxGqxUaQdWC"
    "IYQNez42rCiKE0VxVZigK7pWV6L1RXWSWxnCSSctNawlohFrgbHlYlJUxD/39AoMQVZgLC"
    "lsNNbNWL+I9xBM3nXEFu28tBnhc9YoqMsIB4WeFcWX3zpP+qSS0W3N66weYzMDP5IXMq3h"
    "Nd+ge6M5Wzv+ifBoefFoRWrzGaY27x7KPLreSR9Pxc1HWekPlDvGh8sXg7pyD+aG9Pg4Hv"
    "0u97sN/2hujOXPcm+KzvlHfOjJAj908DMXxRETFZsx8BN+SHIaFvgHWDhwzdZstnLohGAd"
    "ynWjT9VVpnroq5R66KtkPbSgDuno15c6FMHdumld1HaI2o76wcpPbUdl4UyhisXuJwXmHZ"
    "Mn2gLgFWUzomyG87KZWArQ4elge1KUaqKQUpPEokGklC2RGHZDOgZ9/gp/uAEcVex3xB9F"
    "LgoXgtZ0GZiYTlpjugQPA586Fmj962sHbfHcsW6rcLrSfxDwhXPgCmgGZcIIy8VwhrNTaS"
    "uRj/1xp4Xb0WgY4TFuB/EGf7OHW3n8roWhhxfprqmQLBjRdAsvHaoXgd5Y4Fn/xXJ300co"
    "hNbl6HYvYSYRjG7NuD3B6J6j1rMwunFjmZEro4gL3iydN0u4KAnImbmHe2upAOdc9hej3H"
    "cHMBCunVBI74m6gV8qyxCGjLoRW+Y92ErZfS38lHrmpLFdP8GPk5uv+Tem2ITtFFPuRQr1"
    "ENVcAvv06v6EsCjxT6TBQXyQjUe2HsmwRqXSLMcKopsCIrL84rtpGUtm+MIyZw1eFZMwh5"
    "KieMmRLEmYrli34R3MjZFyN8Jpmd7B3JCVProCv6DEW6k3Hfwuo9Rb92huIN9/4CZuekfN"
    "bBNG2TuZ6PbChCvoy1aHA5KWyJTtTAiydeN6rtpZ8vfa9PS9dhzxgCezAEaPDXOytEB9H+"
    "qCYaNDX02uRTBs56j1LAzbyYvsedN1MYl9UUc7J20pNvjNQVoWVkMbpSzryZ1dUIjLLKW1"
    "nBSHVxXq4rhh29kuD09Nm7ij1A32Utlh+hRB4IpT5xM6c5yIJZRIJZMCP+mUsiCQBYHM7Z"
    "xQIIGMR1Xz0cgk2QP5UM7qONnoUBePPIxyUvKccbTB6lndaG+qtja3pFIM6uNOkMz1wHMG"
    "n/e8t1vXH69vrj5cBw99cCbtyReNoevPiAge7By1LjLNeCdtRKaZyDTjH/wjcgkZWYQc/I"
    "FoYn4+nMBp69lObaxEouStTM2FWinNhVrJ5kL+s8WWlhCVqls6QilAu44/xogI9P4squgI"
    "HDfPan7pT7sN+GdufOn30FGvmUsNmbSQooS4DoyF3VJttvlkJ8Ix4rlv9BIQbrMj3BYIsy"
    "B8xY7wlUA4M8I/AfiOCFoayPtn6ugIR8x5/UOWv/SlPxlNPCwmK/1uwzuYG95A7hl4MDfu"
    "/7wdD+Al7isf8/lSe1MN/eXVOUBX8TGOqK0cmsI6wfpQBnf3cJXFL3xqxzEdbaW6VsszIC"
    "iISu4TJAW5T4voPaMtaoGlvppbQtCUjjFRWMBMgDl0NyKcCMRSemiaOECNkC4kOh3CCE7J"
    "B2HsywuIRSyw1lEhEQs8R63TYoGJIFWWWEmEU88fLalrsCrWAKyAuNI55GSXGmUawycFWJ"
    "M3YzHe0rckIlx1kRZjsvD1qg0FVGt7lF2IcDpdaPehXdp/+BMRiuIlFAX/58sLKTE1K30f"
    "iPMcnGpOevdyfzZEtcvB4dx4kJSZNMRb7cLXPARDCTsDLcwNOCikEh2Ba7VAk77bgH/mxu"
    "1oNO1B66Db8I/QhlD3ozHeDgq9cqKe6vUMGM8UJcfGTZ5Yt+EdzI3JrNeTZdwlIDicG5+k"
    "AX6u3FdutGTl8w+ikjX0D6rrDyTdwGfd0O3XXHqOiYrdubjWM3AWSFcLxnz6hNzxymcuS1"
    "Jr0TzwdmMDPOGxYpsUFODGwbXA2vyRA9uEnIA2cd8aa+h+5blvE4ICXCq4boMegrn7eTJS"
    "9uAbko2vrvrCafy7sdLt0pAOeelPW33l6Ib9Hv2/U3jnCKvISutbru8epK9xo7Y3HN3Gl1"
    "A0wG288ZtlmZa6BratvRA8xSn4Rbn/E4J1yJ5JM3bkr9N09ANbZzhS7vzL4yqJon/y7izV"
    "wZ+hOUuupixFNWOpDaIpZT0nbAfCJ7wFdQNJ3sQFIMwWRakovlka2tAjfmVGZCJ9VwixmH"
    "hfFnoUJtwHZm/0pTnfLtqtm/lWW7Q6jfn26fq5Bf/edJaN/2pIXuNEdF676cC/bXCD3txc"
    "QonFc+caCSwXjXdLsNBtOKLdkFqXv71voPEuL+E1H2/QqIubS3jporO8RGP87bqB9hl0r2"
    "kos+HwfZzG4+hrETuk+FtKhhtoR+JSkTgU4mBxdCoorIHPH4j0UhHRKR6iU6LP6H72vPg+"
    "o6I8rcRtkiJTDQPIcbk6uG2xZO1WlmTtFj1ZuxXHGqw1fcUCciBQP3TbnU6WKFunQw+zoc"
    "/IhZaHRUWTo/A8k0DL9G4wmcpjFPTcHc+N6VgauBFT/wiFsB8eh/IUXRochs6qN5fqozzu"
    "yco0dEHobPhaSemrMnwz+jMyXOT83JCl8fDP0HXR93MDRWv6Y+kPlPewO54b/fHo8RGONp"
    "rBrxJ6MzeGsoT6wOMXOP7XR3mIA77+0dyYKV+U0R9Kt+Ed5AkCX2WZaa/oM+1VMghsbq0F"
    "8O2KxL1JpzATggfxl5zNCscmKlHyWb5IfFhQxGd5js/qtuqHrFBHPfz4JNW9b9NT4hBH3P"
    "80OFPZDVArmJwkK+PRcMi+o4kvhzYscY9oi623lgWL2v4lEi7fyuSTPMYrfOhNnmWt+Nwm"
    "YFjmapUypVJM26jYWW/8A+CXZMdvWRR41VmJKDtOWUCz3XKAzI5VRKqG3lWm7irtlO4q7W"
    "R3FVHbRke/mlVOorbtHLVOq23jJvbNm56LSSdAMSFGQEMiIpUgNZXAD7gdGOSewWFqHuIO"
    "3VP8pg9wOgNUOH+gZxo40v9JX4GUfarjF12k71btXg6/wwqIhqHnEwdH+lZZw7IRIZ4jKn"
    "njhWV0tMSggV+EGXgP0J5MLXEuuokWBszW/49EEusv9HKesFiddsL5W7t9dfWxfXn14aZz"
    "/fFj5+YyyOBPfpSWyn87uEOscEQRJJoYfvoC1O/gjeU2j4kVc6dzlEjTumxfZ7rT29cp9z"
    "r6UNA49Xbos9A4riWaR+tRSRH55Ie1cbXM0JKIycEIO4GunU9YHj3RkQGmJvyzvzWPvNwu"
    "NDhz+65GzbztvxjdMjIcBNeMihvdPQOeiOrr7xgNd/z/Bf+tb+uHTuGsQTfXeQ0MeMY91h"
    "GK2wV+L7w8Xry84P45pPtLYhCePZLmg6xMR+Nuw32dGwNlMh3Pevjc7riZw5orPvBOeNKy"
    "ms4EUZ7Vwk2ydAg35lxekmwNA89lpPUmFpB8sAeyNbzXi09Wd3RnxYR0IFBHeMvg9vJtE1"
    "zoBsG8oc6e+8MKX4G7AlcbvAomZ/bH0qcpow3tCqFsS/gyN6TedICqB9zXuSErfTdpE/eO"
    "m8rjh4Ei4ZTN3TEn5p6g7c6QthPZV3XTepbsqx0fwpgwlBAUaUPRWdQl4pALtlmZbwAw4k"
    "sRF7lucZgxuccKblhI3LhkHxjn2jDnZSZlC8T3pDHTUrIJ4495Emzm/DfZG6ruGXCUGTJD"
    "qqEXEDgc6gc8UM0CSwmcw5NlBnRDIZbDER4Eg9Uc5YQ9VUBOJ2VOT6rFD6pmzrAlJG9WcC"
    "rPkGSbXM6y6OWg/Nn4LU8I0RKeCnpwdndnicTZ8wmpGvriO3M7o5BM/QJGxffZWOr2ZoU2"
    "nIXv1Y0FnoEFDFIDgIx719KHOyL1qUgPMivziWS6DfQX7WTb++K9947ysJrFp96+Am250t"
    "lCemGZ+j0QpYSa4L+yzOV24edmRaGmd2eOy9UB7jSesIzmzODXBliOzradfESoDqgfoT59"
    "Y5muRbjOkU1OFK4f8CKpXMQpRHRKaP2Q6NTJCtn5qtYpkHmm00dJsujArXHPIf+exreRmw"
    "Qw0mwsLQK4vGEL6BBQHK0W5uoJlFqMyqfTaS4dLqg0QaUJKk1QaYJKE1RaU1BpgkpLCNUB"
    "dUGlcQF8WVSabqvQetV/5GhZvZM7Yp9q39CsbJtqbbEA8KsZL6oF4M+2iS52GvLkAUSrcA"
    "YdCP6YPutUk0kU/PE5al3wx4I/roIpJ/jjevDHXlvZdBY5edFFeltT3MT1WJRyeDPQnQ3v"
    "9sUJm/RB5XK4fU5URrDTvLDTora/2rX9fC5XGbFbwHtVtYHjrACaJtSNudIXFApnP2tPH4"
    "3nRh/NyXTWl5WpOpb/ZwYXnm4jdgL3AphJQ7U/G0vTwUjBTQHCJ/LQ+sXHYDbamwqxonQA"
    "3q++sDzXCrsfzcbDP7sN93VuPMpjeO1kglUTejM3HkbK9B5d6h3MjeHs4VGdzB66Df8oj/"
    "KKb9qAwLeIsxi1q3BYpE5Nhdut64/XN1cfroNewsGZtBbCSarIMFX7FTqcCChtbW4NwqNB"
    "RZcsfDycLysCsiChj0yALgHGLScdlpQWfXr5YcCSxGegL4hB6vZ1GZIqyENxHG9ryl8fB2"
    "Nvy+YB3qv6QVJmaAdo9xW+x/031b6M+zS5DZmS5/gw0ETogg59NUlsEbo4R61nCV2IbfHq"
    "1SqoPpCmdLMRe7gxtpfYv4cbB31rqgpvlsY1LO1UyoklwV96uzIX36dwCc4UV0oKXGSOMa"
    "HMoSckrKIV/7gRpw2wdHOp4siDCCDxE0CK6IVoYVLow5jcWQeRPDCAQbh790LoSZ01gG5A"
    "0vdDYqnuVA8nKkUDsKLezR5vJuKyEN2VHZdwk5gYkADyThKhUFYVhGWEAg5UQBpBR4a/Ej"
    "wcTwUHgkSjo19NOkWQaOeodUGiCcaHN2wLYXy4oCQmwEFlRnZWRiJ6/QUTIWF7sqWzEYJz"
    "4IVz0FYrOJE7QFvv7oOkCtJL4ShDiGI4loJEDGJLhYC1cuG/ExW4M+Xg4K+ttkyjpa51Y+"
    "sAQrUMNbeMJi6yy2hAu/NEbqDj4gLoONAQHOi4a0v11dxaBIgnazhhUHFOSh8P4fZ1uRBf"
    "tT9+CNBFb9KAnTxIwyFlnoZO6HJrBVVzLPiS5I+H8FXJN3ERCCPiaQOMZXpx/p67mDLG8Z"
    "Bu8Q/0TwC+L7U31YRIeVMqK86UIXLBnIcA/XBZgRvaB2mxMm1wINDxMY6GdKt1XRGoURjk"
    "wFuaMMTRgC6/KqNIoA+9p0ljCKhFmKTWhLkIk5yj1qsXJuGh80QRQRIWHn9/QIV5i7aDwi"
    "k86KD4YEoB/aNnhvZD0zFujzh5a09Dacr1F/s7TKvbnajqJoodI19zl2OMc6tsNKGLZE1u"
    "AicW2ADS4pytgm8nfcQuyCOlx9wFGcl0G+jv3OhLA1SBj1/mxh+y/AW9dV+b2Zbukvsh75"
    "4URqMpIlhDm6m6NlLSNIY+Yx4Vh8SEgrlWsEd22epas7/nZMp2wrWJEBVBJrjrDrRoHH1F"
    "foBoya1RubNutQR/14tpMfXHDsvULz24+AJ7kX4t0q9PiH41GSbBK56j1rPwiqLgvuz0a1"
    "ERXpOK8F1pt7ZCmpIWC9Qybg+7SLn+Yj+7iAvBXVFVc2VF/vX50Ig/tJUO727LXLO4Y1Gp"
    "sy5XdqFgdmhjYmcNoWM62ipHTm5CrjZUS2HJuK/oInZk42IC2DiwWxvkATYuJoBNMoRrOD"
    "ayStjRJcoKiEVGV919cMG8nKPWszAvtrNdoh0U2ByrqNQBDhZntPYhPlTIXkU1YGyAhkQE"
    "mqlElnfrFcBkTdyRarZb2EWMyYo+qhl6R6JbsTCeEP6CKRyv5hiHnl6uucKppRm2hsmpzH"
    "xhQuaCjTN0dvLHyEr0KEr0n0LGqMhL5IZQ9ModGdfHqJRYImMGBwIigWa2TE9flut9mKCR"
    "++mTejeWFLxpVvBmbrhvpP7n2ST4yH03N+5Hwz7au2nYnxtjeShLE7nb8A7mxmwyUO66Df"
    "yCPv80U/roY/TazOYWlLxTE/NOQqfYPahMt6tgXkN7doClBiQQC7BJSYEwFeFXD0ImcH0h"
    "gSuR9Dxyuhl3gMYS87Nl5qel5ot8s9rzX1lYT89fYDRHo1Ii9yidsgn5ZEWRCpRklmqivZ"
    "dfiN5ufFIM9+ZKX2pv+3mFyIUX2ciEV1dGJB6dD0/gqZx5w+24XNGZMzwUPGfMm8GvDDaj"
    "f30NLcZOFoOxQ7cXO8JcFOZiVwTJ66d1WpD8oC4dJdhXY5cB329fRS7MaF+FexAes22Es7"
    "Wb8IpvPr8PrHjgBn2II5L4yBcRZhovZpoFNittAZWVN65DFC8wwMOrvcYS3jE3+oLFkAsE"
    "amjJlcL9LYGjkfLzp+AXtd+zL1ELjNMWa/nrNLJO+0i+e5C+/hZZq4cj5c6/PIR8bzi6TQ"
    "Bu6xae4knt5NMtqbhsDW2p6tpOSZM5pK72AapuF6Tq6iQAVFnTVwdo+kpomntN5+wuf5qu"
    "8uUHeotofeP5NkQzb38az076iA3bHmWlP1DuGD0WX6zb8A7mhvT4OB79Lve7Df8IZeR8ln"
    "tTGefkuEdzoycpPXmIzvlHzRwmZPGZOhb4B1jk44ViomLe43nec5Wl5knHiAnWrwnQVSbH"
    "7CrFMbsiJGWgyW6Vj2aPiooHi+cHy1VWjgcrISgerGwPlghf1SyQIcJX56h1WvhKdNcqlZ"
    "IP4lX56liAAJYCrKidLTERU5R2llDaSZwWCkCZsTyZ0+lgL8DxGTEDyqKXIRPCFehlOAG2"
    "nakoOXLhRbbkFtuVOdmeKG5+y8K08HafO6LWb/gvslm4yWapIAc/6d3L/ZnPhLPU1PqC3U"
    "ZwODcGivo4Ht3BmWHSbYTezI3e6OFxKGNCPjicG8pIndyP/ug2vAN+OXqx98oZ8Ihi75Wa"
    "K9jRnRVTUUMgUIs8rSPkwolsw7IRfjKXhM1Z6LmG/vV1CG0cO9HQNbxVP/GE3jQ0PXElZR"
    "ixHTQB8JypEBFREbHleSF+Mc2XFVDtjbYAKmulIVG4kOntpOn+MRem08niw3Q6dCcGffYX"
    "CfY1AI66tQgp63tBD4vWYUU5HujwHz8DC6Cudt56kPO+pw8kFJJJIdrC2WorFXvmuZYa4g"
    "BiweF5wfFUBl31QzQeFhf65lnfJMo8DytLGqeKOdIQzzFmX72DuQE/Qe/xy9z4NBjK6p2s"
    "yGMJXxZ9Dz+XBpiVdV/54GQjusk5ldPGEE93NZ7uvBM6eQShdZ61LrJO6VNtNfMPRdbpOW"
    "pdZJ2eMuv0VL3Tc+SHcAlpSoakSC07aWpZ4lZPamJkgKkJ/7DmqsbbIlXxXs+aTMmgkGLy"
    "93AiMFg/AWt/Cl/82otsWXw4EXeN5UrI5PsWTvT1txjyWk55b2LJfiJpj5ekvZOVDHA6ax"
    "9oZAgfjQpwRa31LD7aifcB5E3TpRiXJ9u6jlN0i9m77sSlC7saqL1GD6u5U4qdszBfTQvf"
    "g3gRNLbIokpYN0EpgyhO4MvO8fSVQD49fS0mKlovnbBROmfhBdEnXZiTxZuTgvKvm9azUP"
    "6ubcHoQ0SEhAsRmz5FFKVsr2xnEB/olPXwQHX3ySKPqyjW5z2iUpzHK22XujM0X6jObvSC"
    "izQ/V0OXqivz5RhF+Y5mwU/d2wl/CfzWRTi+1QT8FhD9rZ3ciEL4wbz4we5m8iz+2k5ClC"
    "hmLAKNPjOZS0GjYjVEu3gHOTIfZQ5ghYVE16tYfS14hsZFEs7Pk5FCqbANJOIOp75wGv9u"
    "rHS7glWdKWgiKCJOZaLWNl5WG4MdDRCvtcUbebPAHggI1POjrm9YZmj36voRl9dZqsyu6U"
    "Vm14kaM0Fc5rnFOaesiGVlnsXPvAd4TFAsw3t2AQ+7VgeSATMbZKYC+AQ3w6bfsfsrwgbA"
    "b9FQZsPhydgAYOmL1yaJBnA/uUj1/3fXcLObNzV4Sny6CTFTT4ncJpF6AdN26/rj9c3Vh+"
    "sgahqcSQud+lFTul/+A1g2o2MeEqmhr1hO6fuGyd7zLq8huqXwHvA/OsQULboTExI5yI3h"
    "De1j+DEJc+GYi9lf/w9j4NnG"
)
