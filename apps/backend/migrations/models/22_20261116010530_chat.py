from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "mentoring_chat_threads" (
    "id" UUID NOT NULL PRIMARY KEY,
    "last_message_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL,
    "mentor_id" UUID NOT NULL REFERENCES "mentors" ("id") ON DELETE RESTRICT,
    "student_id" UUID REFERENCES "students" ("id") ON DELETE RESTRICT,
    "team_id" UUID REFERENCES "mentoring_teams" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_mentoring_c_mentor__2f1f0d" ON "mentoring_chat_threads" ("mentor_id", "last_message_at");
CREATE INDEX IF NOT EXISTS "idx_mentoring_c_student_194c71" ON "mentoring_chat_threads" ("student_id", "last_message_at");
CREATE INDEX IF NOT EXISTS "idx_mentoring_c_team_id_abb2b2" ON "mentoring_chat_threads" ("team_id", "last_message_at");
        CREATE TABLE IF NOT EXISTS "mentoring_chat_messages" (
    "id" UUID NOT NULL PRIMARY KEY,
    "body" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL,
    "deleted_at" TIMESTAMPTZ,
    "sender_id" UUID REFERENCES "users" ("id") ON DELETE RESTRICT,
    "thread_id" UUID NOT NULL REFERENCES "mentoring_chat_threads" ("id") ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS "idx_mentoring_c_thread__f44232" ON "mentoring_chat_messages" ("thread_id", "id");
-- raw SQL: 채팅방·메시지·읽음 위치 (M23·A57)
ALTER TABLE "mentoring_chat_threads"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_chat_thread_owner" CHECK (num_nonnulls("student_id", "team_id") = 1);
CREATE UNIQUE INDEX "uid_chat_threads_student_mentor"
    ON "mentoring_chat_threads" ("student_id", "mentor_id") WHERE "student_id" IS NOT NULL;
CREATE UNIQUE INDEX "uid_chat_threads_team_mentor"
    ON "mentoring_chat_threads" ("team_id", "mentor_id") WHERE "team_id" IS NOT NULL;
ALTER TABLE "mentoring_chat_messages"
    ALTER COLUMN "created_at" SET DEFAULT now(),
    ADD CONSTRAINT "check_chat_message_body"
        CHECK ("body" IS NULL OR char_length("body") BETWEEN 1 AND 2000),
    -- 지운 메시지는 본문이 없고, 남은 메시지는 본문이 있다
    ADD CONSTRAINT "check_chat_message_deleted" CHECK (("deleted_at" IS NULL) = ("body" IS NOT NULL)),
    -- 시스템 안내(보낸 사람 없음)는 지우지 않는다
    ADD CONSTRAINT "check_chat_message_system_kept"
        CHECK ("sender_id" IS NOT NULL OR "deleted_at" IS NULL);
-- 복합 PK라 Tortoise 모델 없이 만든다
CREATE TABLE IF NOT EXISTS "mentoring_chat_reads" (
    "thread_id" UUID NOT NULL REFERENCES "mentoring_chat_threads" ("id") ON DELETE RESTRICT,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE RESTRICT,
    "last_read_message_id" UUID REFERENCES "mentoring_chat_messages" ("id") ON DELETE RESTRICT,
    "last_read_at" TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY ("thread_id", "user_id")
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "mentoring_chat_reads";
        DROP TABLE IF EXISTS "mentoring_chat_messages";
        DROP TABLE IF EXISTS "mentoring_chat_threads";"""


MODELS_STATE = (
    "eJztXW1z2kqy/isUn85W+aYMNomXuvdWyaDYnPDi5SUnuWFLJcPY1gYkVhJJvLvnv98ZvS"
    "FpZoQkBB6J/mKEUI/h6Xnpfrqn59/1tbFEK+vdAK0fkTnRnvXtZkBu1du1f9d1dY3wBf+h"
    "i1pd3Wx2j5Abtvq4cqWcxxXLed75SH20bFNd2PjTJ3VlIXxriayFqW1szdDxXX27WpGbxg"
    "I/qOnPu1tbXfvnFim28YzsF2TiD779Hd/W9CX6hSzy9lt9a+EP8M2FiVQbLRXVruNnvtUt"
    "W7W3FusTE+FGLXJnYbwYJr5LGt18V540tFpGMNCWpAHnvmK/bpx7s1mv+9F5knzpR9zIar"
    "vWd09vXu0XQw8e32615TsiQz57RjoyyZcJgUF+q4eef8v93fiGbW5R8IOXuxtL9KRuVwTS"
    "+n8/bfUFQbKGlfLOelFNtHynLa13OvqpaMv/9b5lSEJRhqOpMpGnilLPoIyFoRNFarpNkP"
    "/3n267O2ycu3XyDzr30vi3q/d/cdAwLPvZdD50kKv/6QiqtuqKOlrcAe72Gxc8CvkO/nGy"
    "vl076Pfwt1H1BaK0EGsipg78E/Iowr+x08SuL/vA+tClB7s+mc668nDarnkXc32A/47G7Z"
    "r7Wk+livpa/aWskP5sv+C3zcsE1XyWxo52mpeOdgw8MN1xO/Q+aTofESXtlKJri+/ONVMj"
    "7LEQlsmlAq+nH1kDqbt7FOOrNBhf8TG+ojBeatZmpb4q5L2yMdETMpHXu/MMgoTmBNZGfS"
    "gN5HaN/J3rw17nk/feu8ozGhppNNXga6pBaWqt2osXBU9p5BflVE+8DZF1MpCmnXu5i6ck"
    "9wJrZqQ411gz3tVclwa3vbvZaDZp14JLMWavnSGQazUJpE+3kNQf5GG3N7zLuHT7Yu2ad4"
    "G18vAwHn0myvOv5vpY/l3uTMk9/0oMPZnoh4Z+unYapawuhtjW1oi92MREY5paerLv/Ath"
    "xlYRxta0N5AnU2nwQJpfW9Y/Vw5e0lQmnzSdu6+xu7+9j+klaKT2R296XyNva/83GspxCy"
    "54bvp/dfKd1K1tKLrxU1GXYUz82/6tmJ7/gRY2nvxUC4OQwaSgBAWeNXPbFekMiyTLghpY"
    "If8n47iKShYwrE5kV6dHH//A5UhfvXodoyTjzOvDicNsu1nm1HpUErQuitYZs6v37cOTa5"
    "TbULIxGBzxAygNwabbQ1iL0NiykJkR2ZBIkQRRaeEklNvTdyYH5DN6UWg/GibSnvVP6JUy"
    "2GOAesTlDDcTEJblxHV3dzeSTPVnQFSGexUGAP9WZDsQjPE8Mu51pvXEyaEAkDtOQ2lhFn"
    "My2IsyZ1bkIE569qO6+P5TNZdKpIuTT4ymEbsTPEt/tG6u43dUXX12kCI/ifwATxEjaWu/"
    "SIuFsdVtLpdPP3SRxOUbeKV5UVT3+SNw+d/qG9P4oS3d4e7+N/8Owdhh6/3ZIHj077EQAJ"
    "D3opD3YW3m4VrC8kLT9p+kT9KoXXNe5vrdaHTXl9s193WuD6XP8piwmPhFDGqFHlpMDbEH"
    "BlNYZPXk9L2brVYa3FstPvDkM/C9q+2Fge99jlpP43uDVwheoRD+Cs8r7EiTjtSV38pF2U"
    "HPcE0ieuG7JOSnHT+rCFwKUVwKtFa1VRZrNRAoxkLdD3i57dMX1XrB5sZGtayfhpnJL2CI"
    "Vi8gdxTQM+dSHZJHJdoiFsW3lcbXbfF93Rbl624wREjRtyQNNQvIcblC+rJA00ejkSYRqs"
    "FPhGrEkX7UTPtFIb4I28th4xyVSvJwyjd3JCBMHJQYfnh9No0f6ko5LEOJ0QykKh2XT3Mh"
    "z+Xgx0QhVUkch57mcRxjUvmBTA3/nDzaZjYAOhdZ564dcIDOmQ2AzkXWuWYpKvaZfzAMmV"
    "vDWCFV5zj4YbmYih+x4LFW3eDOafV6Oxr1Iyq97U1ji+ZscCtjM9LRJX5Ic4mn3nAaW0FX"
    "qmUrK+NZ03OMMEoYRpfIo8slIPNMpVFJ0LLIWoZIJ1fNJY15QaTzHLXOi3RSoTl+ECkU3K"
    "F2g8esK0/+46cxWqkOwnRnSNqIXrI+wYvgMbJ1wml3+UFjZvxVBbRjBisfkLnWLAt/VW7I"
    "Mv7IRVLgchM8DOHL8wlfLnBHyBKE8J+vXPCykWpjWyNhY1uD3tgW/mYUyFP0y+Z5FRGxKg"
    "Qtk2wL+cs0Ylb4kP42kL78JWJa9EfDO//xkAo6/dEtKzfnaFkkoR0LxgoxVsCBqr9ODfI3"
    "ZdbPGLeTe/l702GUkPPj/DYltihFfqlJ7ANsYwfcZnQRejJMRx/f0asPtpc2FKjK+2gn6D"
    "1gv5jG9vklEIu1zEw7wveVMPbBGs5dhHc/hrH8Rn4pf+ENuhAsubDkntOSW3xqBeStHBFc"
    "MGZOacwAc5mu05eTw+Ixl7k4LCebmmOIZqFiSIbzQXaoGMOycBomFHqPmaeH2fwMeqZUq3"
    "lWy5/xe+P2/64XRy1/yryP2/8h16AIy383GhM3CySa/9RwSt40oJzGD/hWtxbGBrl9EX/k"
    "viN7mcFDEMVDiGooT8pltAWRzdv6HbZ3pH675r7O9dvRaNrBC2e75l/N9c7ofjSetmvuaz"
    "2HOXyEqn3+wMkwNsIyULImiif6tdHwp3lyGCOSkIQhTlwWkjDO15WJ1PXZWWdpp8qQCGw8"
    "hupeRcOZsI+b9Dwa2sz7uKvoSV/E607tBmmK6l6wQb7Asmlvs0P+1jDshbreTGz16Ynr+T"
    "Keukhyfx+958kGsaeno9TxQuvNynhFTrfy/51DQJDBHi/Y9W33CHjFwnjF7Hk5nT/sywrt"
    "CQ+koXRHCnN5F3Ndmkx62PQi528El2J4v2DH86Gvrh0fTNTZJr+YGBigcerDW5wywhoTA1"
    "iT7fqwCXCgCSp7TVXdDI31sBQ2fti2OhBk34qsOsix2VEoe9+tnpxs7VPPJNr6XoHi01j6"
    "uyrSHDsfztcDKx+sfLDywcoPaz3PwRxFHcchmp7BwhcMVrDw39bCf6OTOcoKsLgHcnTRRj"
    "XtNUo4jiP+SKJlvwweht0s52OvY51jjWdc1yJCkAgFm1hO5tEkbmLhY1zEJhaxoW6l2v/c"
    "Stj/3KL3P5tb5qYE/mahQAC2CcE2IfDWocDROWqdkUibv8CR7+AduDesqv7wUUv0REFj+F"
    "cUqnzvKqJH8K3OwrdydU486oM2AzGaEdmArY/lu1lfGpOa6s4F2f8znI6ljrMDyL2a673h"
    "VB4P2zX3da4/SOOpQmZW5ffRbbsWeTvXP45luS8NOyTwsrue612p1//arjkvEHMRfBIv6X"
    "oOVtw5ap1nxUXZCJ8yzUigUYIQGoqfsmNYmr3bL56amYyKAazCbj0SofRBseHL3aAuILrG"
    "CN2Us8PujbBRc2GKIKY/zAuMFD94TVYd7tgMmTmkycgm3yUD5ico2HuOKqIDVnpOEaCxUj"
    "erAhlN7OzbiTjS0dTAf06xD1GE1avoXYiFcGXRaTSBM6Pm2/3cmeLPXUCinQ+J9rbhdIHK"
    "bRZPVW1MzTA1+5WGd7JWV6uezonyhuViMGuu8VuyRQh/X/zyX1fND+9v8KfOdyRvPiQgPh"
    "lI/T597hTQf3yUy0kEAf13jlqHIG7Fgrhj9KyRf0u+tGSRA4MSU2fTiKUzWs1QC4oaNAE2"
    "7PnYsLApDjbFlWGCLulaXYrSF+VJbs0QTnrTrYaVRDRiLWQsuUiLQvxzT63AEGQFxpLCRm"
    "PVjPWLeA1ButcxS7SLUmZEzFmjoCojAmz0LCm+4u7z5E8qKd3WvM7qKQ4z8CN5IdMaP/MN"
    "uzeqvbXin4BHK4pHC6nNZ5javBuUeXS9kz6diusP8rDbG95lHFy+GNaVezHXpYeH8eiz3G"
    "3X/Ku5PpZ/lztTcs+/EkNPJvqhoZ+5KI6YKBzGIE74geY0TPQPtLDxmq1a2bZDU4JV2K4b"
    "HVVXqfZDXyXsh76i90MDdchHv7rUIQR3q6Z12NsBezuqB6s4eztKC2cCVQynnxSYd8yeaA"
    "uAF7bNwLYZwbfNxFKADk8H25OiVBGFHDVJLBpESjgSKcNpSKegz1/wD9eRrcB5R+JR5LBx"
    "IShNl4KJaSUVpqN4GDzqskDrP185aIvnjjVLwdOV9oOBL54DV0jVORNGWC6GM56djrYS+d"
    "ifdlq4HY36ER7jthcv8Dcb3Mrj3xoO9PghzTUV6A0jqmY6S4fiRaA3JnrSfmXp3fwWCqF1"
    "BeruR5hJgNGtGLcHjO45aj0Noxs3ljNyZRxx4M2SeTPKRaEgz8w93JvLIbLP5XwxTr87gI"
    "Fw7YRCak9UDfyjsgxhyLgHsaU+g+0op6+FR6lnTurb9SP+mD58ze+YcAjbW0y5FwnUQ1Rz"
    "FPbJu/spYdjiT6XBYXyIjce2HtmwRqWSLMcSopsAIrH84qdp6cvM8IVlzhq8MiZh9qXh0E"
    "uOzJKE6Yq1a97FXB8N70ZOWqZ3MdflYZc84byQxFupM+19lknqrXs114nv33MTN72reroJ"
    "49gnmWjWwsAr6PNWww2ylsiE40wYslXjeq6aafL3mvz0vWYc8YAnM5GDXjbM2dKA+j7UgW"
    "HjQ19OrgUYtnPUehqG7c032Yum62IS+6KOdk7aEg74zUFaFraHNkpZVpM7u+AQl2m21gqy"
    "ObysUBfHDVv2dnl4atrEbaVqsB+VHeZPEQyuOHE+4TPHVCzhiFQyK/CTTCkDgQwEsrBzQo"
    "EEstOqko9GZskeyIcKto8zGx3q4pGHUaYlzxlHC62elI36qqhrY8vaisEd7gzJXANeMPi8"
    "8d5sXH+4vrl6fx0M+uBO0siHwtDVZ0SABztHrUOmmeikDWSaQaaZ+OCfkEtIySLk4A+giP"
    "n5cAJvu5/trY2VSJS8kaq4UCOhuFCDLi7kj61saQlRqaqlIxwFaNfxdzBiAr0/iyragsDF"
    "s+qfutN2Df+Z65+6HXLVqedSQyotJCghrgN9YTUUK9t8shMRGPHcHf0ICDezI9wEhLMgfJ"
    "Ud4StAODXCPxH6TghaHsj7Z+poCyfMef1Dlj91pa8ZTTxHTB522zXvYq57Dbl38MVcv/96"
    "O+7hR9xXMebzpfqq6Nrzi32AruJtnFBbOTTl6MTRx7B3d49XWedFTO3Yhq2uFNdqeUIMBX"
    "HJfYYkkPu8iN4TOaIWmcqLsWUETfkYM4UBZgbMod5IcGIQS8mhaWYDFUK6kOh0CCM8JR+E"
    "sS8PEEMssNJRIYgFnqPWebFAKkiVJlYS4dTzR0uqGqyKFQArIK50DjnZR40yjfFIQebkVV"
    "+Mt/wjiRhPXSTFmEznecXCAoq5PckpRE46Xej0oV3af/gTCEWJEorC//P5mZWYmpa+D8RF"
    "Dk7VJ517uTvrk73LweVcH0jDmdR3jtrFr3kIhiOcDLQwNuigkEq0BaHVgk36dg3/meu3o9"
    "G0g62Dds2/IgdC3Y/GznFQ5FUQ9ZSvZsB4NhzmOLjJE2vXvIu5Ppl1OrLsVAkILuf6R6nn"
    "jCv3VRgtmfn8g6hkBf2D8voDtBv4pOma9ZJLzzFROJ1LaD0je0F0tciYT0/JnW77zOWR1F"
    "o0D7zdWMiZ8LJiSwsCuHFwTbQ2fuTAlpIDaKl+q6+x+5Wn31KCAC4XXLdAD8Pc/X0yGu7B"
    "NyQbX121hV37T22lWUdDOuSlP261la3p1jvy/97COydYRVZa33L9bSB9iRu1nf7oNr6Ekg"
    "Zu44XfTNMwlTWyLPWZ4SlO0S9O/6cEq5A9k2TsyF+myegHtk5/NLzzH4+rJIr+m1dnKQ/+"
    "GYqz5CrKUlQxlsogmrCt5w3LgYgJb0HVQOhOXADC2aIoJcU3TUEbfsTvmBGZSN0VRiwmXp"
    "eFH4UJ14HZG32pz7eLZuNmvlUXjVZtvn28fmrgvzetZe1/apJXOJHcV29a+G8T3ZA3N5dY"
    "YvHUuiYCy0XttyVaaBZu0apJjcu/vKuR9i4v8TMfbkiri5tL/Oiitbwkbfz1ukbOGXSfqQ"
    "1n/f67OI0n0NdiVkjxj5QMF9COxKUicSjCwTrRqWBjDR5/KFJLBaJTIkSnoM7ofva8+Dqj"
    "sD3tiMckRaaaDCDH5argtsWStRtpkrUb/GTtRhxrtFa1VRaQA4HqodtstdJE2VotfpiNfM"
    "beaHlYVJRuReSZBFumd73JVB6ToOfueq5Px1LPjZj6VySEPXjoy1PyaHAZuqvcXCoP8rgj"
    "D6ehB0J3w89Kw64i4zejr5HmIvfnuiyN+19Dz0Xfz3USremOpT9I3sPueq53x6OHB9zaaI"
    "a/SujNXO/LEqkD77zg9r88yH0n4OtfzfXZ8NNw9MewXfMu8gSBr9LMtFf8mfaKDgIbW3OB"
    "fLuC6pt8CpMSPIi/FGxWODVRSZLP8kXiw4IQnxU5PqtZih+yIhX1nOFDq3vfoafMJk54/m"
    "lwp7QHoJYwOUkejkf9fvYTTXw5cmCJe8VbbL21LFjU9i+RePkeTj7KY2eFD73Js6wVn9uE"
    "dNNYrRKmVI5pGxU764N/EP6S2fFbFgVeeVYizolTJlItdztAascqIlVB7ypVdZVmQnWVJl"
    "1dBfa28dEv5y4n2Nt2jlrn7W0TJvYtmp6LSScgMaGMgIZEIJUgMZXAD7gdGOSe4WYqHuIO"
    "9Slx0wcEnQFKnD/QMXQn0v9RW6GEc6rjD10kn1btPo6/wwpBwdDziYMTfStZw7IRIZEjKn"
    "njhceoaOmAhn4xZuA9QHsylcS56CJaDmCW9i8WSaw987fzhMWqdBLOX5vNq6sPzcur9zet"
    "6w8fWjeXQQY//VFSKv9t746wwhFFsGhi/OkzUr6j1yzdPCZWTE8XKJGmcdm8TtXTm9cJfZ"
    "18CDROtR36NDSOa4nm0XpUEiKf4rA2rpYzlCTK5GCEnUDXzmcsj57oSEdTA//ZX5pHXm4X"
    "Kp65fVejYt72nxndMjYcDNeMixvfPUOeiOLr7xQFd/z/hf+tb+uHbjlZg26u8xrp+I57rR"
    "EUtwvnPXh5onh5Qf85pPoL1YjIHkl9IA+no3G75r7O9d5wMh3POs693XU9hzVXfOCdMdLS"
    "ms4MUZHVIkyydAi3zLm8LNkKBp6PkdZLLSD5YA9kK9jXi09WtzV7lQnpQKCK8B6D28t3TH"
    "ChBwSLhnr23J+s8BV4KnC5wSthcmZ3LH2cZrShXSGSbYlf5rrUmfbI7gH3da7Lw66btOnU"
    "jpvK40FvKDkpm7trQcw9oO3OkLaD7KuqaT1N9tWOD8mYMEQJQtpQdBZ1iTjigm1WxitCGf"
    "HliEOuWxxmh9zLCm5YCDou2wd2cm0y52XSsgXi+6Yx06NkE8aHOQ125vw32Wuq6hlwnBky"
    "RaqhFxA4HOqB01DFAksUzuHJMgW6oRDL4Qj3gsYqjjJlTxWQ08mZ02m1+EHV1Bm2jOTNEk"
    "7lKZJs6eUsjV4Oyp+Nd3lGiJYxKvjB2V3PgsTZ8wmp6trie+ZyRiGZ6gWMiq+zsdSszYoc"
    "OIvfKxsTPSET6awCACnPruU3d0LqcygN5KzMJ5Fp18hfcpJt55P33rvKw2oWn3r7gtTlSs"
    "sW0gvLVG9AHCXUhP+VaSy3Cz83Kwo1vzpzXK4KcCfxhMcozox+bZBpa9mOk48IVQH1E+xP"
    "35iGaxGuc2STM4WrBzwklUOcAqJToPVDolNvtpFdrN06BTLPfPqIJosOPBr3HPLveXwbu0"
    "hARpotS4kAITtsARUCiqPVwlw9g1KLUfl8Os2lw4FKAyoNqDSg0oBKAyqtDlQaUGmUUBVQ"
    "BypNCOCPRaVploKtV+1HjpLVO7kT1qn2Dc3SlqlWFwuEv5r+rJgI/2yL6WInIc9uAEqFZ9"
    "AB8Mf8WaecTCLwx+eodeCPgT8ugykH/HE1+GOvrGwyi0w/dJFc1tQp4noqSjl8GOjOhnfr"
    "4oRN+mDncrh8TlQG2GlR2GnY21/uvf1iLlcpsVvgvqpYyLZXiEwTysZYaQsOhbOftee3Jn"
    "Khj/pkOuvKw6kylv82wwtPuxa74dQCmEl9pTsbS9PeaOgUBQjfyEPrFx+D2aivCsaKUwF4"
    "v/rC8kIr7H40G/e/tmvu61x/kMf42cnEUU3ozVwfjIbTe/KodzHX+7PBgzKZDdo1/yqP8o"
    "ov2kDAN5mzGLeqcFikSkWFm43rD9c3V++vg1rCwZ2kEsI0VaQbivWCHU4ClLo2tjpjaHDR"
    "ZQufDufLkoAMJPSJCdAlcnDLSYfR0lCnVxwGjCY+A31hDBKPr0uRVMFuSuB4W13+8tAbe0"
    "c295yzqgfScEZOgHZf8Xun/qbSlZ06TW5BJvqeGAYahC740JeTxIbQxTlqPU3oAo7Fq1ap"
    "oOpAmlDNBs5wy1heYv8ZbgLUrSkrvGkK12Qpp3KcWBL+pbcrY/F9ipfgVHElWuAidYyJZA"
    "49EmGFrPinjThtkKkZS8WJPEAASZwAUkQvTAuTQx/G5M46iOSBgXRG790LoSd11gC6AUnf"
    "D4mlunM9nKgUD8CSejd7vJmIy8J0V3Zcwg01MRAB4p1QodCsKgjLgAIOVEASQceGvxQ8nE"
    "gbDoBE46NfTjoFSLRz1DqQaMD4iIZtIYyPEJTEBNlkm5GVlpGIPn+RiZCwPNmjsxHAOYjC"
    "OairFZ7IbaSud/2AVkHyVjhOE7AZLsuGRAfEhoIBa+TCfycKuGfKwXG+ttIw9Iay1vStjR"
    "i7Zbi5ZTxxyC7jAe3OE7mBjosD0HGgMTjYcVeXyouxNRkQT9Z4wuDiTEufDuHm9XEhvmp+"
    "eB+gS94kATsZSP0+Z57GTuhyawa75rLgy5I/HcJXR+7ERSBMiKcN0pfJm/P39GJOG6dDui"
    "E+0D8R+r5UXxUDI+VNqVlx5jSRC+Y8BOj7yxJ0aB+kxcqw0IFAx9s4GdKNxnVJoCZhkAO7"
    "NKOJkwF9/F0ZRQJ9aJ9mtQFQQ5ik0oQ5hEnOUevlC5OIUHmiiCBJFh5/f0Al8xFtB4VTRN"
    "BB8cGUAupHz3T1h6o5uD04yVt7Ckpznr/YX2Fa2e5EFTdR7BT5mrscYye3yiITOiRrChM4"
    "MdEGsRbndDv4dtInrII8GnYyV0EmMu0a+TvXu1KP7MB3Xub6H7L8ibx1X+vplu4j10PejZ"
    "SMRlNEsII2U3ltJNo0xj5jHhWHxEDBQivYI7ssZa1a33MyZTvhykSIiiAT3HUHWzS2tmIP"
    "IF5ya1TurEst4d/1bJiZ6mOHZaqXHlz8BntIv4b06zdEv5wME/CK56j1NLwibLg/dvo17A"
    "ivyI7wIJFaMm3tKah2zeUVqScv9jOKJC1F9YSOQCV+q1vIsrzkoqWp/UCKezjL0iUQIzQj"
    "7o/21gJmURxmMaqxDCYwJShy7c+8pnCrlcYUbrX4pjD5LJbU541FFykm4vspXaoRkdGvf+"
    "515VG75rzM9elYGk46497DtF3bXc/1yWwwkMZf2zXvIg/LW3yFVaeHZz0HMiJUQRfxGONi"
    "jQ35hDHByyAOCVUP6KMcMOh0Tkv7F6v0qvbM5TojYhVKm/prs3l19aF5efX+pnX94UPr5j"
    "LgPemPkljQ294d4UAjiqBJUc8Eyjnv76RPGMp7kIfd3vAuazTPEyO1tZ2Luf4wHnVIjW3n"
    "ZnA91zujwUNfdopwBpdz/aPU65Nb7qsYqwHwWHzoy8loAI91jlpPw2N5fm1GIisqBUxWMp"
    "MV4g4KobKcPelOk1UntaL9TExW61ZdEaVJiwU5CGE/t8V6/iIdw/XoiiqqKwtVBc6Hwvqh"
    "rjTcu01jzV6d2cBHpc66CJ8LReY0jZjYWUNoG7a6yrHTnJKrTAJRYVvMX8hD2ZGNiwGwcW"
    "C3FsoDbFwMgKXz3ta4bWKVZEeXKQsQwz7FqnvkwMOco9ZT8TD2dknOBc3Iw0SkDnCwBIta"
    "HOJDhexVUtkoG6AhEUAzmdRyu14BpNbEbSktlyUmuPuprMhQTXEiCumKRVKGU9xexTEOjV"
    "6hucKpqeqW6pBTqflCSuYiG2do7+RPsdfWoyjJfwoZo5ATJwyh6BXxyrg+RqVgiYwZHAck"
    "u5Uixw0buR8/KndjaegcBR+8mevuG6n7+2wSfOS+m+v3o36XnEje7871sdyXpYncrnkXc3"
    "3mpkrM3CyJsfxxNuySj8nrXB99lsfEvG7X/Kt6OlfhyDkSmc/Mfotzso+fV1QY16E+2chU"
    "AmIoC7C0JCDMRfjFgzATuL4Q4MokQk+8sVI4QI+fzQlMKB/9cnJiaZhQz4fIaKJGpSA3KZ"
    "nGCflpRRENnASXcqK9l3OIdjcxaQe8FNkDZFn4sf18A/XwRTqiYYHllLUreAqGwX4hMx/5"
    "R/4uPCAWRCAWHo0lo5DHFP3imJj+81XY2JK0+MpfppF11zd4fhtIX/4SWXv7o+Gd/3jIQO"
    "r0R7dgFxWhCoHsIEZskDaE3CUlj5qjkgWouUQDrmxathDGMGtJiYgQ8LExPtYxEbKGgMNC"
    "4D4kuw87I6wo74GYn1On1ap7DpGOliIg7A71ArCeWSh1ORQx54UUG0dC06K4Tlm4o+/zyW"
    "KDIrVL5naz09ZXXqlW4As6cd+L2rdwxgjzcz/hgfoQfDtRfLu4ajJaowxxMElFNknBv+Sq"
    "ucK8O9S2K9wTgfReSO8VD01I74X03hJhvD+9l17FCoO46mxECeqH3hsrbam+7neXIw9epP"
    "OVX1wZqKlwPt6sp3LF37xP+zds6ONyRRcFEOGEMhbUjJIAWWtGHlQuUrSpNZr41kqT99bi"
    "p721IOsNvO827P+tntYZVJvz7Sn3643tq7G7uWe/fRV5MKV95e0cOvk5j04pdhJe8L6AG0"
    "EL70kLYg9elAKqt4tlpplos1IXWFl5t6wxxQvkf0S117JwacZGW2Qx5AKBClpyR9nCsES2"
    "yio9xk+M3ElUAuNT50bir6mZzhSvNLJaUnHZCtpS5bWdWPmRgbqaB6i6WZCqxaRXq6bpqw"
    "M0fQWaFl7TW4w7s2py8mm1Ybkq7Vct4qzacz6WQXp4GI8+k6MW/CtSbOB3ueOcyOBfzfWO"
    "NOzIzpEM/lU9hwlZfMEBE/0DLfLxQjFRmPdEnvdcZSl5dpXHBKuwoSp+KnK6Y5GTzkWmWX"
    "Yy2a3y0exRURhYIg8sV1k5BhYlCAMr3cCC8FXFAhkQvjpHrfPCV5AyfFRKPohX5SvRV8Sm"
    "0GoCC3nDx9wQCmmtx01rjYSxT5uaLeh0sBfg+IwIycNnmDwcOTEvKbklfrRemuQW75y6ky"
    "e3mLYVpLCYaGGYS+fbBEQt0pcWbKEVKpulhBz8pHMvd2c+E56lXLAv2K4Fl3O9N1QexqM7"
    "PDNM2rXQG94RycORMrkf/dGueRficvS7EUmpN9n1jQhW0PMtr6dLExz+nJpRxSExULDQCr"
    "Y1e5VpU0MgUIk8rRPkwkG24bERhiKMp0s0dA1vxU884Z+HmJy4ktBMrjwWwbRSYBqLi1TO"
    "VIiIKERsRV6Inw3jeYUUa6MukJJ1pyFTuJDp7U3T/WMuTKuVxodptfhODPnsTxbsa4RsZW"
    "syUtb3gh4WrcKKcjrQ8T9+QiYiB3Z560HOfs9vCBSSSiHqwt6qK8XxzHMtNcwGYMERecHx"
    "VEZqRx6g8bA46FtkfbMo8zysLKudMuZIYzzHDvvqXcx1/Al577zM9Y+9vqzcyUN5LDmPRd"
    "/jz6Wew8q6r2JwshHd5JzKeW3A6C7H6M47obNbAK2LrHXIOuVPteXMP4Ss03PUOmSdvmXW"
    "6VsdC50jP0RISBMyJCG17E1Ty6iuTmtipKOpgf9kzVWNl0UqY19Pm0yZQSGF5u8NDTvFGY"
    "bUwxeZ8vjwemOf4AxDSMoTJSnvpOFyQWfik8XLwUPjqqKktjp4aOeo9TQemr+gZj3UMCwF"
    "7sRhlUIpbRRn8cb3SpRRHSnOkgv3xlNavLa9QsQ47dloncbopZ9Pbff6ooqGZU+xj2X3L2"
    "F3ijiGMNG+Cx2Fe7pQaKQBkc3j+kSeTHqjYbvmXdAbTcQIYIbG5sZYaQuGo5Jy7xCrIbFV"
    "NJ115eFUGct/m+GZlsSlIzfmutSZzqS+0p2NpamjzNiNPCq8SlcLJaEUCpWNrbnQ8VODuV"
    "nBLNEqlbVrNq4/XN9cvb8OkoKDO0mZwXRS8EZ9VfBvY3gX6UZHWF7oQXE/mo37X9s193Wu"
    "P8hjJZjLQm/m+mA0nN6TR72Lud6fDR6UyWzQrvlXYsxxBHwCbYaBERaBAcEYEOra2LIOcO"
    "MiuhMAPBl4Am3Fh7qcBEYa2mphvBhm1nBoRAhCzHyDNistFBMEaClogW478rmoO9qCQjh/"
    "laMddVP1cD41hiN8WkeadKSuXGdMwQXA3XEaqjrCkcWn0IQJoI/LSR9noY5z0sZHYIzDpY"
    "52U0Bo/lgbOnZH/04xy/seBqZZBKaZ0g0FP/8AVpZs0YewijHbs0BnHMNawqJS3bH0cZqx"
    "y7pC7ZrzMtc7/dHEKQLlvIrBZPmz/SIj+ULJnY6DuTxSFy6agLENW13loNApOYCWDW1mxj"
    "AuBsBSpOHKsPJxhmFB2HEmTooT7DgDYpg0AfmMVdN6mnxGCAcUzlnDJj7YcSYUYZdmxxnw"
    "08Lw00egTp1DJ9D6EZn7qdP4sxfpqFPn0Ie1I3cU7jR0qITlnvLgVokP3sBeNEGJ0Tc7nk"
    "bQCeVA8wK8My7AJbXT03hn3jSXNREiIgVDaU8qhLeUHG74nMk5RNHuJbDpk87oyWruHMXO"
    "2RnfziKob4lFxQgKez4QBIDFsnM8fVHIJ5dKj4lWKV25iProWUsGV7cycCtNfLfFj++24F"
    "BjMCeB7K+g1oHsB7K/vJAmeGXARhfORsPBsMJU7yvO45W2S83uG89cZzf6wEWSn6uSR5WV"
    "8XyKwhm2auJPgxoL3lsX4ZCN6bD9+Ftg9LeW6yeFPwU/WBQ/WHV+ShZ/bSch8kb1nC7bcQ"
    "4cjI6ZtEDHxCqIdvEOcmQ+Sh3ACgsdMJsIRkYUYzM/oidsXNBw/j4ZDdlw7iTiDqe2sGv/"
    "qa00q4QnCCagSaCIOJVUncp4ScoY7KSBeJ1K9clmUZN82AMBQD0/6tomywztPl094vI6zY"
    "lm1/wDza6p88yAuMzTxQWnrGimcmfxZ1yCKUFYhhN5lqhrdSAZMLNQaipATHD3MgFU/4qw"
    "Afhb1Iazfv/N2ABkaouXOosGcD+5SPT/d88IUy+eGzxljm5GzNRT4mG++vEDpgdu1eL75T"
    "+Qya52wLdGQiIV9BWPc8zqJpO95z1eQXSPwnvg/2gzU7T4TkxI5CA3RjS0T+HHUObCKRez"
    "P/8fKlPeQg=="
)
