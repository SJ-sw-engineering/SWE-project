# 출석 API · ESP32 Wi-Fi 연결 · Swagger 테스트

2026-11-01 / 코드 버전 0.4.0

## 1. 구현 범위와 출석 규칙

- 팀장이 출석을 시작하면 서버가 숫자 6자리 문자열과 5분 만료 시각을 만듭니다.
- 같은 팀에 진행 중인 출석은 하나입니다. 모집이 마감된 팀도 출석을 진행할 수 있습니다.
- 팀장과 승인된 팀원이 회차/이력을 조회할 수 있고, 전체 팀원 현황은 팀장만 조회합니다.
- 인증 대상은 ApprovedMembers에 등록된 팀원입니다. 팀장은 정원에 포함되지만 출석 인증 대상에서는 제외합니다.
- 일반 회차·이력 응답에는 code를 넣지 않습니다. 인증된 장치만 코드를 받습니다.
- 코드가 맞고 서버 기준으로 만료되지 않았으면 출석을 저장합니다. 같은 유효 요청을 재전송하면 같은 기록과 최초 인증 시각을 반환합니다.
- 5분은 출석 시작 시점부터 계산합니다. display_ack는 LCD 표시 상태이며 출석 입력을 허용하는 필수 조건은 아닙니다.
- 현재 승인된 팀원 기준으로 이력 명단을 구성합니다. 회차별 참여자 명단을 별도 스냅샷 테이블에 저장하지 않습니다.
- 미출석은 기록 없음으로 표시하고, 새로 is_present=0 행을 만들지 않습니다.
- 팀원별·회차별 인증 요청은 서버 프로세스당 분당 5회입니다. 성공과 중복 요청도 포함합니다.
  한도를 넘으면 429와 Retry-After를 반환합니다. 이 제한은 단일 worker 배포용 메모리 방식으로 재시작 시 초기화됩니다.
  출석/장치/회차 데이터와 중복 방지는 DB에 유지됩니다.

## 2. DB 변경 여부

기존 Devices, AttendanceSessions, AttendanceRecords의 컬럼과 UNIQUE(session_id, member_id)를 그대로 사용합니다.
새 테이블·컬럼 추가가 없으며 총 8개 테이블을 유지합니다. 001·002 SQL을 다시 실행하지 않습니다.

[003_attendance_precheck.sql](../migrations/003_attendance_precheck.sql)은 **읽기 전용 확인 SQL**입니다.
SQL Editor에서 전체 실행하여 다음을 확인할 수 있습니다.

1. 기존 출석/장치 3개 테이블에 총 18개 컬럼이 표시됩니다.
2. AttendanceRecords에 NON_UNIQUE=0, session_id/member_id 조합의 인덱스가 있습니다. 이름은 기존 DB와 ORM에서 달라도 됩니다.
3. 중복 기록과 팀별 진행 중인 회차 중복 조회는 각각 0행이어야 합니다.

앱은 시작 시 스키마나 데이터를 자동으로 초기화하지 않습니다.
현재 DB와 다르게 컬럼이 누락된 별도 DB라면 해당 결과를 확인하고 DB 담당자와 구조를 먼저 맞춥니다.

## 3. API 계약

사용자 API는 기존 Bearer 접근 토큰을 사용합니다.

| 메서드·경로 | 권한 | 용도 |
| --- | --- | --- |
| POST /api/posts/{post_id}/devices | 팀장 | 장치 등록 및 인증키 1회 발급 |
| GET /api/posts/{post_id}/devices | 팀장 | 장치 목록; 인증키 제외 |
| POST /api/posts/{post_id}/attendance-sessions | 팀장 | 출석 시작 |
| GET /api/posts/{post_id}/attendance-sessions | 팀장·승인 팀원 | 회차/이력 목록, 본인 기록 |
| POST /api/attendance-sessions/{session_id}/close | 팀장 | 출석 종료 |
| GET /api/attendance-sessions/{session_id}/records | 팀장 | 팀원별 출석 현황 |
| POST /api/attendance-sessions/{session_id}/check-in | 승인 팀원 | 6자리 코드 인증 |
| GET /api/devices/{device_id}/display | 장치 인증키 | 표시할 활성 회차 조회 |
| POST /api/devices/{device_id}/ack | 장치 인증키 | 실제 LCD 표시 완료 응답 |

### 장치 등록과 인증키

POST /api/posts/{post_id}/devices는 본문 없이 호출하고 201을 반환합니다.

```json
{"id":1,"post_id":6,"last_ack":null,"device_credential":"esp_발급된_기기키"}
```

device_credential 원문은 이 응답에서 한 번만 반환합니다. ESP32의 로컬 config.h에 보관합니다.
DB에는 sha256:로 시작하는 해시를 저장하고 장치 목록 API에는 원문과 해시를 모두 제외합니다.
장치 요청에는 다음 헤더를 사용합니다.

```text
X-Device-Key: 발급된 device_credential 원문
```

학생 로그인 토큰, DB 비밀번호, JWT_SECRET_KEY를 이 헤더에 넣지 않습니다.
기존 DB에 수동으로 만든 평문 device_credential이 있으면 이 버전은 인증하지 않습니다. 등록 API로 새 장치를 만들고 그 ID/키를 사용합니다.
키를 잃어버렸을 때도 새 장치를 등록하면 됩니다. 한 팀에 장치를 여러 개 등록할 수 있지만 활성 출석은 하나입니다.
last_ack는 마지막 표시 완료 응답 시각이며 실시간 온라인 상태를 뜻하지 않습니다.

### 출석 시작

POST /api/posts/{post_id}/attendance-sessions:

```json
{"device_id":1}
```

201 응답과 회차 목록의 각 항목은 다음 필드를 사용합니다.

```json
{
  "id":1,"post_id":6,"device_id":1,"leader_id":"팀장아이디",
  "status":"OPEN","display_ack":false,
  "start_time":"2026-11-01T00:00:00Z","expiry_time":"2026-11-01T00:05:00Z",
  "my_record":null
}
```

이미 활성 회차가 있거나 다른 팀 장치이면 409입니다. 출석 종료는 본문 없이 호출하며 200과 같은 형태의 CLOSED 회차를 반환합니다.
종료 요청을 반복해도 200입니다. GET 회차 목록은 최신 회차 ID부터 배열로 반환합니다.
만료 시각이 지나면 즉시 인증을 거부하며, 조회/표시/다음 시작 등의 요청에서 DB status를 CLOSED로 정리합니다.
별도 cron이 없으므로 요청 없이 SQL로만 보면 만료된 행의 status가 잠시 OPEN일 수 있습니다. 활성 여부는 expiry_time도 함께 판정합니다.

### ESP32 코드 조회

GET /api/devices/{device_id}/display + X-Device-Key:

```json
{
  "server_time":"2026-11-01T00:00:02Z",
  "poll_after_seconds":2,
  "session":{
    "id":1,"code":"000047","expiry_time":"2026-11-01T00:05:00Z",
    "expires_in":297,"display_ack":false
  }
}
```

활성 회차가 없으면 session=null, poll_after_seconds=10입니다. JSON을 반환하며 204가 아닙니다.
앞자리 0을 유지하도록 code는 정수로 바꾸지 않습니다.

### 표시 완료 응답

POST /api/devices/{device_id}/ack + X-Device-Key:

```json
{"session_id":1}
```

200: `{ "session_id": 1, "display_ack": true }`.
LCD에 실제 출력한 회차 ID를 보냅니다. 다른 장치 회차는 403, 종료/만료 회차는 409입니다.
유효한 같은 ACK를 재전송해도 200이고, 장치 last_ack가 갱신됩니다.

### 팀원 코드 인증과 기록

POST /api/attendance-sessions/{session_id}/check-in + 팀원 Bearer:

```json
{"code":"000047"}
```

200:

```json
{"id":1,"session_id":1,"member_id":"팀원아이디","is_present":1,"checked_in_at":"2026-11-01T00:01:00Z"}
```

그 후 팀원의 회차 목록에는 my_record에 이 기록이 포함됩니다.
팀장용 GET /records는 `{ "member_id": "...", "name": "...", "record": 기록또는null }` 배열입니다.
일반 팀원에게 다른 사람의 출석 명단을 제공하지 않습니다.

| 오류 | 의미 |
| --- | --- |
| 400 | 형식은 6자리지만 코드 불일치 |
| 401 | 사용자/장치 인증 실패 |
| 403 | 팀장 권한 없음 또는 승인 팀원 아님 |
| 404 | 존재하지 않는 회차/모집글 |
| 409 | 활성 출석 중복, 잘못된 팀 장치, 종료/만료 |
| 422 | 코드가 6자리 숫자 문자열이 아님 등 입력 오류 |
| 429 | 회차·팀원별 분당 5회 초과 |

## 4. Swagger 테스트 순서 (실기기 없이 API부터 확인)

코드를 push/배포한 뒤 Render /docs 버전 0.4.0을 확인합니다.
팀장 한 명과 승인된 팀원 한 명이 있는 테스트 팀을 준비합니다.
팀 구성 방법은 [지원·승인 안내](applications-and-activities.md#3-swagger--실제-tidb-테스트-순서)를 참고하세요.
모집글 ID를 P로, 아래에서 얻는 장치 ID는 D, 회차 ID는 S로 기록합니다.

1. 팀장으로 로그인하고 Authorize의 HTTPBearer에 접근 토큰 문자열을 넣습니다.
2. POST /api/posts/P/devices를 실행합니다. 201의 id(D), device_credential(K)를 로컬에 기록합니다.
3. Authorize의 DeviceKey 칸에 K를 넣습니다. HTTPBearer와 별개이며 접두어 Bearer를 붙이지 않습니다.
4. GET /api/devices/D/display를 실행하면 시작 전에는 session=null입니다.
5. POST /api/posts/P/attendance-sessions에 `{ "device_id": D }`를 입력합니다. 201의 id(S)를 기록합니다.
6. GET /api/devices/D/display에서 session.code를 확인합니다. 일반 회차 목록에는 이 코드가 없어야 합니다.
7. POST /api/devices/D/ack에 `{ "session_id": S }`를 보냅니다. 이 단계는 실기기 표시 응답을 Swagger로 모의하는 테스트입니다.
8. 팀장으로 회차 목록을 조회하면 display_ack=true여야 합니다.
9. 승인 팀원으로 로그인하고 HTTPBearer를 팀원 토큰으로 교체합니다. 체크인 API에 받은 코드 문자열을 보냅니다.
10. 200을 확인하고 한 번 재전송합니다. 같은 기록 id와 checked_in_at이어야 합니다.
11. 팀원 회차 목록에는 my_record가, 팀장 토큰으로 GET /records에는 해당 팀원의 record가 표시되어야 합니다.
12. 팀장 토큰으로 POST /attendance-sessions/S/close를 실행합니다. 이후 장치 display의 session=null이고 이력은 유지됩니다.
13. 같은 회차 체크인/ACK는 409입니다. 새 회차를 시작하면 이전 기록은 남고 별도 회차 ID를 받습니다.

추가 확인:

- 잘못된 키/키 없이 기기 조회 → 401.
- 승인되지 않은 사용자/팀장의 체크인 → 403.
- 팀원의 전체 명단 조회/종료 → 403.
- 같은 팀에서 출석을 다시 시작 → 409.
- 정상 길이의 틀린 코드 → 400, 3자리 코드/숫자 타입 → 422.
- 새 회차에서 같은 팀원이 6회 요청 → 여섯 번째 429. 정상 인증 테스트와 섞이면 요청 수가 누적되므로 60초 대기하거나 별도 회차를 사용합니다.
- 새 회차를 종료하지 않고 5분 기다린 뒤 조회 → CLOSED, display session=null, 체크인 거부.

## 5. 실제 TiDB 확인

아래 123/456/789를 실제 P/D/S로 바꾸고 묶음 전체를 선택해 실행합니다.

```sql
USE recruitment_db;
SET @post_id = 123;
SET @device_id = 456;
SET @session_id = 789;
SELECT id, post_id, last_ack, device_credential LIKE 'sha256:%' AS credential_hashed
FROM Devices WHERE id = @device_id;
SELECT id, post_id, device_id, status, display_ack, start_time, expiry_time,
       TIMESTAMPDIFF(SECOND, start_time, expiry_time) AS duration_seconds
FROM AttendanceSessions WHERE id = @session_id;
SELECT id, session_id, member_id, is_present, checked_in_at
FROM AttendanceRecords WHERE session_id = @session_id;
```

- 기기 등록: credential_hashed=1, last_ack=null.
- 출석 시작: 해당 팀/장치 ID, OPEN, display_ack=0, duration_seconds=300.
- ACK: display_ack=1, last_ack에 시각 표시.
- 팀원 인증: is_present=1인 행 하나. 재인증해도 행이 늘지 않음.
- 종료 또는 만료 후 조회: CLOSED이고 기록은 남음.
- 테스트 모집글 삭제: 기존 외래 키 CASCADE에 따라 해당 장치·회차·기록도 제거됨.

## 6. 프론트 담당자 연결

기존 로컬 함수와 대응합니다: devices → GET devices, startAttendance → POST attendance-sessions,
sessions → GET attendance-sessions, closeAttendance → POST close, roster → GET records, checkIn → POST check-in.
필드 이름과 배열 구조는 기존 로컬 화면에 맞췄습니다.
addSimulator 버튼은 실제 장치 등록 기능 또는 별도 준비 절차로 바꾸고, 서버 모드의 LCD 시뮬레이터는 실기기로 대체합니다.
브라우저의 표시 확인 버튼 대신 실제 ESP32가 ACK를 보냅니다. 기기 키를 공개 JS 코드에 넣지 않습니다.
서버 모드의 출석/이력 페이지 제한을 풀고, 상세의 팀장 여부는 기존 /context의 is_owner를 사용합니다.
현재 3초 화면 갱신을 유지할 수 있습니다. 장치와 일반 사용자 요청의 인증 방식을 혼동하지 않도록 연결합니다.

## 7. ESP32 연결 방법과 현재 한계

Arduino 예제와 Wi-Fi 설정은 저장소의 [firmware 안내](../../firmware/README.md)를 확인하세요.
네트워크 흐름은 ESP32 → Wi-Fi 공유기/핫스팟 → HTTPS Render → TiDB입니다.
ESP32가 서버에 요청하므로 공인 IP나 포트 포워딩을 장치에 설정할 필요는 없습니다.
ESP32에는 DB 비밀번호나 사용자 JWT를 넣지 않습니다. 네이티브 HTTP 클라이언트이므로 CORS 주소 등록도 필요하지 않습니다.
USB는 업로드/전원/Serial 확인에 사용할 수 있고 출석 데이터 통신은 Wi-Fi로 진행합니다.

사용자가 LCD 예제를 나중에 제공하기로 했으므로, 현재 예제는 모델/주소/핀을 가정하지 않는 LCD 어댑터를 포함합니다.
기본 상태에서는 받은 코드를 Serial에 표시하고 **실제 LCD ACK는 보내지 않습니다**.
LCD 함수를 연결한 후에만 실제 출력/ACK/만료 시 화면 지우기를 실기기에서 검증할 수 있습니다.

## 8. 검증 범위

2026-11-01: SQLite 102개 + 로컬 MySQL 8개, 총 110개 테스트 통과입니다.
현재 TiDB의 세 테이블 필수 컬럼 누락은 없고 UNIQUE(session_id, member_id)도 확인했습니다. 스키마/데이터는 변경하지 않았습니다.
SQLite 독립 API 테스트와 로컬 MySQL에서 권한/코드 비노출/중복·만료/ACK/이력을 검증합니다.
MySQL 테스트는 실제 출석 시작 동시 요청과 체크인 동시 요청, 6자리 앞자리 0, TIMESTAMP/ACK, DB 삽입 오류 시 롤백을 포함합니다.
Arduino 예제는 ESP32 Dev Module 대상으로 실제 설정을 채운 경우의 Wi-Fi·HTTPS 코드 전체 빌드까지 통과했습니다.
검증은 임시 가짜 설정으로 컴파일만 수행했으며 실제 사용자 보드 업로드와 LCD 출력은 별도 실기기 단계입니다.
코드 작성 중 실제 TiDB에는 읽기 전용으로 구조를 확인하고, 출석 데이터를 생성하거나 스키마를 바꾸지 않습니다.
