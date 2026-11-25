# 백엔드 구현 기록

| 번호 | 작업 | 상태 |
| --- | --- | --- |
| 01 | [백엔드 프로젝트 세팅과 CI](01_backend_project_setup.md) | 완료 (#3) |
| 02 | [docker compose 로컬 개발 환경과 S3 에뮬레이터](02_local_docker_compose_and_s3.md) | 완료 (#4) |
| 03 | [P1-1 identity·audit 모델과 첫 마이그레이션](03_p1_1_identity_audit_models.md) | 완료 (#6) |
| 04 | [docker compose 백엔드 마운트 수정](04_fix_compose_backend_mount.md) | 완료 (#7) |
| 05 | [P1-2 academy 모델](05_p1_2_academy_models.md) | 완료 (#8) |
| 06 | [P1-3 organization 모델](06_p1_3_organization_models.md) | 완료 (#9) |
| 07 | [수강생 명단(student_rosters)을 students에 합침](07_merge_student_rosters_into_students.md) | 완료 (#10) |
| 08 | [P2-1 인증 기반과 운영진 Google 로그인](08_p2_1_auth_google_login.md) | 완료 (#11) |
| 09 | [P2-2 운영진 최초 정보 입력](09_p2_2_staff_registration.md) | 완료 (#12) |
| 10 | [P3-1 역할·권한 모델과 최고 관리자 CLI](10_p3_1_roles_super_admin_cli.md) | 완료 (#13) |
| 11 | [Google OAuth 콜백을 백엔드가 받도록 변경](11_oauth_backend_callback.md) | 완료 (#14) |
| 12 | [테스트 DB를 격리된 TortoiseContext와 전용 DB로 관리](12_isolated_test_database.md) | 완료 (#15) |
| 13 | [P3-2a 권한 판정과 require_permission 의존성](13_p3_2a_permission_checks.md) | 완료 (#16) |
| 14 | [P3-2b 운영진 가입 신청 승인·반려](14_p3_2b_staff_registration_review.md) | 완료 (#17) |
| 15 | [P3-3a 과정·기수 담당자 관리 API](15_p3_3a_staff_assignment_api.md) | 완료 (#18) |
| 16 | [P3-3b 회원 역할 관리 API](16_p3_3b_user_role_api.md) | 완료 (#19) |
| 17 | [P4-1 조직(부서·직위·직원) 관리 API](17_p4_1_organization_admin_api.md) | 완료 (#20) |
| 18 | [P4-2 학사(HRD 과정·회차, 운영과정, 기수) 관리 API](18_p4_2_academy_admin_api.md) | 완료 (#21) |
| 19 | [P5-1 과정 별칭 컬럼과 Airtable 클라이언트](19_p5_1_airtable_client.md) | 완료 (#22) |
| 20 | [P5-2a Airtable 명단 레코드 해석과 동기화 서비스](20_p5_2a_roster_sync_service.md) | 완료 (#23) |
| 21 | [P5-2b 명단 동기화 동시 실행 락과 taskiq 작업](21_p5_2b_roster_sync_worker.md) | 완료 (#24) |
| 22 | [P5-2c 명단 동기화 관리 API](22_p5_2c_roster_sync_api.md) | 완료 (#25) |
| 23 | [P5-3 과정-기수 테이블로 학사 마스터 동기화](23_p5_3_cohort_master_sync.md) | 완료 (#26) |
| 24 | [워커 Redis 읽기 타임아웃으로 인한 반복 종료 수정](24_fix_worker_redis_socket_timeout.md) | 완료 (#27) |
| 25 | [P5-4 수강생 테이블 실구조 확인과 레코드 링크 매핑](25_p5_4_student_link_mapping.md) | 완료 (#28) |
| 26 | [P6-1 S3 어댑터와 S3 시나리오 통합 테스트](26_p6_1_s3_adapter.md) | 완료 (#29) |
| 27 | [P6-2 멘토·강사·계약·계약서 모델](27_p6_2_educator_models.md) | 완료 (#30) |
| 28 | [P6-3 계약서 업로드와 계약 관리 API](28_p6_3_contract_api.md) | 완료 (#31) |
| 29 | [P6-4 계약 수동 연결과 멘토 프로필 API](29_p6_4_contract_link_mentor_profile.md) | 완료 (#32) |
| 30 | [P7-1 메일·SMS 발송 기반과 Gmail 드라이버](30_p7_1_notification_senders.md) | 완료 (#34) |
| 31 | [P7-2 수강생·멘토 가입 (인증코드·레이트 리밋·가입 신청)](31_p7_2_member_signup.md) | 완료 (#35) |
| 32 | [P7-3 가입 자동 매칭과 승인 알림 메일](32_p7_3_signup_auto_matching.md) | 완료 (#36) |
| 33 | [P7-4 수강생·멘토 로그인, 잠금, 비밀번호 재설정](33_p7_4_password_login_reset.md) | 완료 (#37) |
| 34 | [P7-5 수강생·멘토 가입 승인 관리와 재신청](34_p7_5_signup_approvals.md) | 완료 (#38) |
| 35 | [P8-1 기수 멘토링 설정·금지 시간대·추가 휴일](35_p8_1_mentoring_settings.md) | 완료 (#39) |
| 36 | [P8-2 기수 멘토 배정·멘토 활성화·팀리드 권한](36_p8_2_cohort_mentors.md) | 완료 (#40) |
| 37 | [P9-1 멘토 불가 시간·신청 받기·기수 운영시간](37_p9_1_mentor_schedule.md) | 완료 (#42) |
| 38 | [P9-2 신청 가능 시간 계산·조회](38_p9_2_available_times.md) | 완료 (#43) |
| 39 | [P10-1 멘토링 팀 구성](39_p10_1_mentoring_teams.md) | 완료 (#44) |
| 40 | [P10-2a 멘토링 시간 계좌·지급·조정·조회](40_p10_2a_balance_accounts.md) | 완료 (#45) |
| 41 | [P10-2b 명단 동기화 후 수강 종료 처리](41_p10_2b_enrollment_ended.md) | 완료 (#46) |
| 42 | [멘토링 유형(평시/프로젝트) 제거](42_remove_mentoring_period_type.md) | 완료 (#47) |
| 43 | [P11-1 멘토링 신청·시간 보류·조회·승인 전 취소·대기 만료](43_p11_1_mentoring_requests.md) | 완료 (#48) |
| 44 | [P11-2 멘토링 승인·반려·세션 생성](44_p11_2_mentoring_approval.md) | 완료 (#49) |
| 45 | [P11-3a 승인 후 취소·운영진 취소·변경](45_p11_3a_mentoring_cancel_change.md) | 완료 (#50) |
| 46 | [P11-3b 신청 연동 (불가 시간 충돌·멘토 변화·수강 종료)](46_p11_3b_mentoring_integrations.md) | 완료 (#51) |
| 47 | [P12-1 Google Meet 공간 생성·막기](47_p12_1_meet_spaces.md) | 완료 (#52) |
| 48 | [P12-2 Meet 이벤트 구독·실시간 수신·처리](48_p12_2_meet_events.md) | 완료 (#53) |
| 49 | [P12-3 Meet 멘토 공동 주최자 등록](49_p12_3_meet_cohost.md) | 완료 (#54) |
| 50 | [P13-1 세션 기록·내부 메모·미제출 목록](50_p13_1_session_records.md) | 완료 (#55) |
| 51 | [P13-2 녹화·전사·요약 수집·폴더 정리·중계](51_p13_2_meet_artifacts.md) | 완료 (#56) |
| 52 | [P14-1 정산 집계·조회·마감](52_p14_1_settlements.md) | 완료 (#57) |
| 53 | [P14-2 정산 CSV 내보내기·멘토 정산 조회](53_p14_2_settlement_export.md) | 완료 (#58) |
| 54 | [P15-1 채팅방·메시지·읽음·운영진 열람](54_p15_1_chat.md) | 완료 (#59) |
| 55 | [P15-2 채팅 실시간 수신(SSE)·멘토링 이벤트 안내](55_p15_2_chat_stream_notices.md) | 완료 (#60) |
| 56 | [운영진 신청·세션·채팅방 목록 필터](56_admin_list_filters.md) | 완료 (#63) |
| 57 | [운영진 멘티 목록·신청·세션 수 집계](57_mentee_list.md) | 완료 (#64) |
| 58 | [refresh 재사용 유예 시간](58_refresh_reuse_grace.md) | 완료 (#73) |
| 59 | [계정 종류(account_type)와 운영진 로그인 실패 경로](59_account_type.md) | 완료 (#75) |
| 60 | [조직 구조: 부서·팀과 직위 담당 방식](60_org_teams.md) | 완료 (#79) |
| 61 | [조교 담당 기수는 비어 있는 기수만](61_cohort_assistant_filter.md) | 완료 (#80) |
| 62 | [수강생 멘토링 신청 준비 API (BE-1)](62_student_mentoring_prep.md) | 완료 (#81) |
| 63 | [계정 종류를 수강생·멘토·운영진으로 나눔](63_account_type_member_split.md) | 완료 (#82) |
| 64 | [신청 응답 보완: 단건 조회·확정 세션·취소 주체·차감 상태](64_request_response_supplement.md) | 완료 (#84) |
| 65 | [신청 목록 상태 여러 개 필터와 상태별 건수](65_request_list_counts.md) | 완료 (#85) |
| 66 | [세션 응답 보완: 실제 진행 시각·참여자·취소·차감·상태별 건수 (BE-2a)](66_session_response_supplement.md) | 완료 (#91) |
| 67 | [녹화 서명 링크와 스마트 메모 마크다운 (BE-2b)](67_artifact_link_markdown.md) | 완료 (#92) |
| 68 | [Meet 전사 문장 저장·조회 (BE-2c)](68_transcript_entries.md) | 완료 (#93) |
| 69 | [세션 목록 상태 여러 개 필터 (BE-2d)](69_session_list_statuses.md) | 완료 (#94) |
| 70 | [녹화 끝 시각 (BE-2e)](70_artifact_recording_end.md) | 완료 (#96) |
| 71 | [내 정보 비밀번호 변경 링크 (BE-2f)](71_password_change_link.md) | 완료 (#98) |
| 72 | [내 팀 응답 보완 (BE-2g)](72_my_team_summary.md) | 완료 (#101) |
| 73 | [채팅 자격을 신청 이력 기준으로 (BE-2h)](73_chat_request_history.md) | 완료 (#103) |
| 74 | [세션 목록 정렬 (BE-2i)](74_session_list_order.md) | 완료 (#106) |
| 75 | [멘토 받은 신청 보완 (BE-2j)](75_mentor_request_cohort.md) | 완료 (#108) |
| 76 | [멘토 세션 목록 탭·기수 필터 (BE-2k)](76_mentor_session_views.md) | 완료 (#111) |
| 77 | [기록 제출 시 잔여 부족 처리 (BE-2l)](77_record_overtime_shortfall.md) | 완료 (#113) |
| 78 | [불가 시간 충돌 응답에 주제·신청자 (BE-2m)](78_schedule_conflict_detail.md) | 완료 (#116) |
| 79 | [정산 응답에 기수·항목 상대·주제 (BE-2n)](79_settlement_labels.md) | 완료 (#119) |
| 80 | [CI 시간 줄이기](80_ci_speedup.md) | 완료 (#121) |
| 81 | [CI 변경 감지: 이전 커밋이 통과했을 때만 건너뛰기](81_ci_change_base_fix.md) | 완료 (#123) |
| 82 | [운영진 유효 권한·담당 기수 (BE-3)](82_staff_access.md) | 완료 (#125) |
| 83 | [가입 수동 승인 후보 (BE-3b)](83_approval_candidates.md) | 완료 (#127) |
| 84 | [직원 목록 검색·팀 필터·담당 (BE-3c)](84_employee_list_assignments.md) | 완료 (#130) |
| 85 | [역할별 권한 DB 판정·역할 관리 API (BE-3d)](85_role_permission_management.md) | 완료 (#132) |
| 86 | [권한 엔터티 × 조회/관리 세분화 (BE-3f)](86_entity_permissions.md) | 완료 (#134) |
| 87 | [직위 = 역할, 최고 관리자 필드, 데이터 범위 (BE-3g)](87_positions_as_roles.md) | 완료 (#135) |
| 88 | [담당 역할 칸 제거·직원 수정에서 담당 지정 (BE-3h)](88_staff_assignments_without_role.md) | 완료 (#136) |
| 89 | [직원 목록 전체·최고 관리자 함께 수정 (BE-3i)](89_employee_list_all.md) | 완료 (#139) |
| 90 | [직원 응답에 직위 데이터 범위 (BE-3j)](90_employee_data_scope.md) | 완료 (#140) |
| 91 | [부서·팀 직원 수 (BE-3k)](91_org_employee_counts.md) | 완료 (#142) |
| 92 | [부서·팀·직위 영향 조회 (BE-3l)](92_org_impact.md) | 완료 (#143) |
