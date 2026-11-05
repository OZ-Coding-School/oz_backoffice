-- 최초 컨테이너 기동 시 1회 실행된다 (postgres-data 볼륨이 비어 있을 때).
-- btree_gist: EXCLUDE 제약에서 uuid = 와 tstzrange && 를 함께 쓰기 위해 필요

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 통합 테스트 전용 DB (TEST_DATABASE_URL=postgres://oz:oz@localhost:5432/oz_backoffice_test)
CREATE DATABASE oz_backoffice_test OWNER oz;
\connect oz_backoffice_test
CREATE EXTENSION IF NOT EXISTS btree_gist;
