#!/bin/sh
# 로컬 S3 에뮬레이터 초기화: 버킷 생성 + CORS 설정 (멱등)
# docker-compose.yml의 s3-init 서비스(amazon/aws-cli)가 실행한다. 에뮬레이터 종류와 무관하게 S3 API만 사용한다.
set -eu

ENDPOINT="${S3_ENDPOINT_URL:?}"
BUCKET="${S3_BUCKET:?}"
REGION="${AWS_REGION:?}"

echo "S3 에뮬레이터 대기: ${ENDPOINT}"
i=0
until aws --endpoint-url "$ENDPOINT" s3api list-buckets >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge 60 ]; then
    echo "S3 에뮬레이터가 60초 안에 응답하지 않았습니다." >&2
    exit 1
  fi
  sleep 1
done

if aws --endpoint-url "$ENDPOINT" s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
  echo "버킷 존재: ${BUCKET}"
else
  aws --endpoint-url "$ENDPOINT" s3api create-bucket --bucket "$BUCKET" \
    --create-bucket-configuration "LocationConstraint=${REGION}" >/dev/null
  echo "버킷 생성: ${BUCKET}"
fi

aws --endpoint-url "$ENDPOINT" s3api put-bucket-cors --bucket "$BUCKET" \
  --cors-configuration file:///init/cors.json
echo "CORS 설정 완료"
