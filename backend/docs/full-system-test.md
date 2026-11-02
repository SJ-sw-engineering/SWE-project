# 전체 수동 테스트: 새 계정 → 팀 모집 → ESP32 LCD 출석

2026-11-02 / API 0.4.0. 이날 공개 Render /openapi.json에서 0.4.0과 API 28개를 확인했습니다.
이 문서는 테스트 절차이며, 이 절차를 작성하면서 실제 계정을 생성하거나 DB 데이터를 변경하지 않았습니다.

## 0. 준비와 기록

- Swagger: https://swe-project-u3f0.onrender.com/docs
- 일반 창은 팀장, 시크릿 창은 팀원으로 같은 Swagger를 엽니다. 같은 일반 창의 탭 두 개 대신 브라우저 세션을 분리합니다.
- 모든 요청은 API를 펼친 뒤 Try it out → 입력 → Execute 순서입니다. 응답의 Server response Code를 확인합니다.
- GET/본문 없는 POST는 별도 JSON을 만들지 않습니다. 경로의 {post_id} 등은 Swagger 입력 칸에 실제 숫자를 넣습니다.
- Authorize의 HTTPBearer에는 access_token 문자열만 넣습니다. Bearer 접두어와 따옴표를 붙이지 않습니다.
- 토큰 교체: HTTPBearer의 Logout으로 입력을 해제 → 새 토큰 입력 → Authorize. 이 버튼은 서버 로그아웃 API와 다릅니다.
- 기기 인증은 DeviceKey에 장치 원문 키만 넣습니다. HTTPBearer/refresh_token/장치 키는 서로 다릅니다.
- 접근 토큰은 기본 30분입니다. 중간에 401이면 다시 로그인해 해당 창의 토큰을 바꾸고 GET /api/users/me로 본인을 확인합니다.
- 기존 DB 초기화, 원본 DROP/INSERT SQL, 이미 적용한 001/002 SQL, 비밀번호 해시 변환을 다시 실행하지 않습니다.

| 기록할 값 | 얻는 응답 |
|---|---|
| L_ACCESS / L_REFRESH | 팀장 로그인 응답 |
| M_ACCESS / M_REFRESH | 팀원 로그인 응답 |
| P | 주 테스트 모집글 id |
| Q | 거절·수동 마감·삭제용 모집글 id |
| A / B | 팀원의 P / Q 지원서 id |
| D / K | 장치 등록 id / device_credential |
| S0 / S1 / S2 | Serial / LCD 출석 / 만료 테스트 회차 id |

P/Q/A/B/D/S는 설명용 이름입니다. JSON에는 실제 숫자를 넣고, K/토큰은 응답 문자열을 사용합니다.
아래 username이 이미 있으면 끝 숫자를 바꾸되 이후 요청과 SQL도 같은 값으로 바꿉니다.
두 계정에 별도 팀장/팀원 권한을 부여하는 API는 없습니다. 글 작성자는 그 글의 팀장이고 승인된 지원자는 그 팀의 팀원입니다.

## 1. 서버 확인

일반 창에서 GET /health → 200, GET /health/db → 200을 확인합니다.
DB 상태가 503이면 회원가입 전에 Render 환경변수/DB 연결부터 확인합니다.

## 2. 팀장 가입·로그인·내 정보

POST /api/auth/signup:

```json
{"username":"e2e_lead_1102","name":"전체테스트팀장","password":"E2eTest!1102"}
```

201, username/name/created_at 응답, password 미포함을 확인합니다. 같은 요청을 한 번 더 보내면 409입니다.

POST /api/auth/login:

```json
{"username":"e2e_lead_1102","password":"E2eTest!1102"}
```

200 응답의 access_token/refresh_token을 L_ACCESS/L_REFRESH로 기록하고 HTTPBearer에 L_ACCESS를 등록합니다.
GET /api/users/me → 200, username=e2e_lead_1102인지 확인합니다.

## 3. 팀장: 모집글 작성·조회·수정

POST /api/posts:

```json
{"title":"E2E1102 출석 연동 검증","content":"팀장과 팀원 한 명으로 전체 기능을 확인합니다.","category":"Web/Frontend","target_size":2}
```

201의 id를 P로 기록합니다. current_size=1, target_size=2, status=RECRUITING이어야 합니다.
GET /api/posts/P → 작성 내용 확인.
GET /api/posts/P/context → is_owner=true, my_application=null.
GET /api/users/me/teams → P의 role=LEADER.

GET /api/posts에서 page=1, page_size=10, keyword=E2E1102, category=Web/Frontend, status=RECRUITING으로 실행합니다.
items에 P가 있어야 합니다. 사용하지 않는 선택 검색 칸은 비웁니다. 정원 도달 후에는 CLOSED 조건으로 조회해야 합니다.

PATCH /api/posts/P:

```json
{"title":"E2E1102 출석 연동 검증 수정완료","content":"수정 API 확인을 완료했습니다."}
```

200과 수정된 내용을 확인합니다. status/current_size는 RECRUITING/1을 유지합니다.
팀장으로 POST /api/posts/P/applications에 {"message":"본인 글 지원 테스트"} → 409를 확인합니다.

거절·수동 마감용 글도 POST /api/posts로 만듭니다.

```json
{"title":"E2E1102 거절 마감 삭제 검증","content":"주 출석 팀과 분리한 테스트 글입니다.","category":"Web/Frontend","target_size":3}
```

201의 id를 Q로 기록합니다. **P는 아직 수동 마감/삭제하지 않습니다.**

## 4. 팀장: 장치 등록과 ESP32 통신 준비

POST /api/posts/P/devices는 본문 없이 실행합니다. 201의 id=D, device_credential=K를 기록합니다.
GET /api/posts/P/devices → D가 있고 last_ack=null, 인증키는 응답에 없어야 합니다.
팀장 Swagger의 Authorize → DeviceKey에 K를 입력합니다.
GET /api/devices/D/display → 200, session=null입니다.

ESP32 준비는 [firmware 안내](../../firmware/README.md)의 Arduino IDE 절차를 따릅니다.

1. esp32 by Espressif Systems 3.x, ArduinoJson 7.x, hd44780 by Bill Perry를 설치합니다.
2. firmware/attendance_display/attendance_display.ino를 엽니다.
3. 같은 폴더의 config.example.h를 config.h로 복사합니다. 기존 config.h가 있으면 값을 수정합니다.
4. Wi-Fi/실제 D/K를 넣고 우선 LCD_ENABLED=0으로 둡니다. SDA=21, SCL=22, LCD_I2C_ADDRESS=0입니다.
5. 일반 ESP32-WROOM-32 개발 보드는 ESP32 Dev Module과 연결된 COM 포트를 선택합니다. 기존에 성공한 정확한 보드 설정이 있으면 그것을 사용합니다.
6. Verify → Upload 후 Serial Monitor를 115200으로 엽니다. 필요하면 EN/RESET을 누릅니다.
7. Wi-Fi 연결 → 시간 동기화 → HTTPS display: 200 → Server: no active attendance session for DEVICE_ID=실제D.를 확인합니다.

.ino와 헤더는 같은 폴더에 둡니다. 헤더는 include되어 함께 컴파일되므로 따로 업로드하지 않습니다.
실제 설정을 채운 config.h는 Git에 올리지 않습니다. K는 사용자 JWT/DB 비밀번호가 아닙니다.

## 5. 새 시크릿 창: 팀원 가입·로그인

POST /api/auth/signup:

```json
{"username":"e2e_mem_1102","name":"전체테스트팀원","password":"E2eTest!1102"}
```

201 후 POST /api/auth/login:

```json
{"username":"e2e_mem_1102","password":"E2eTest!1102"}
```

M_ACCESS/M_REFRESH를 기록하고 **시크릿 창** HTTPBearer에 M_ACCESS를 입력합니다.
GET /api/users/me → 팀원 계정.
GET /api/users/me/applications → 새 계정이면 [].
GET /api/users/me/teams → 새 계정이면 [].
GET /api/posts/P/context → is_owner=false, my_application=null.

## 6. 팀원: 두 글에 지원

POST /api/posts/P/applications:

```json
{"message":"전체 기능 검증을 위해 지원합니다."}
```

201, status=PENDING, applicant_id=e2e_mem_1102 확인. id를 A로 기록합니다.
같은 요청 반복 → 409. 지원 중복 행을 만들지 않습니다.
GET /api/users/me/applications → P의 PENDING 항목.
GET /api/users/me/teams → 아직 P가 없어야 합니다.
GET /api/posts/P/context → my_application.id=A/status=PENDING.
GET /api/posts/P → 아직 current_size=1.

POST /api/posts/Q/applications도 같은 형식으로 실행하고 id를 B로 기록합니다.

팀원 권한 검사:

| 요청 | 기대 |
|---|---|
| PATCH /api/posts/P + {"title":"권한 검사"} | 403 |
| GET /api/posts/P/applications | 403 |
| PATCH /api/applications/A + {"status":"APPROVED"} | 403 |
| POST /api/posts/P/devices | 403 |

## 7. 팀장: 승인·거절·마감

일반 창 GET /api/users/me로 팀장인지 확인합니다.
GET /api/posts/P/applications → 팀원 이름/message/PENDING이 있는지 확인합니다.
PATCH /api/applications/A:

```json
{"status":"APPROVED"}
```

200, APPROVED. GET /api/posts/P → current_size=2, status=CLOSED(정원 2, 팀장 포함).
GET /api/users/me/teams → P는 LEADER.
같은 A를 다시 APPROVED/REJECTED 처리 → 409.

PATCH /api/applications/B:

```json
{"status":"REJECTED"}
```

200, REJECTED. GET /api/posts/Q/applications로 확인합니다.
POST /api/posts/Q/close를 본문 없이 실행 → 200, CLOSED, current_size=1.
반복 close → 200. 정원 미달인 Q로 수동 마감을 별도로 확인한 것입니다.

시크릿 창의 팀원 확인:

- GET /api/users/me/applications → P는 APPROVED, Q는 REJECTED.
- GET /api/users/me/teams → P는 MEMBER, Q는 없음.
- GET /api/posts/P/context → is_owner=false, my_application.status=APPROVED.

모집 마감 CLOSED와 출석 회차 CLOSED는 별개입니다. 모집이 마감된 P에서도 출석을 진행합니다.

## 8. Serial 전용으로 첫 출석 시작 (S0)

ESP32의 LCD_ENABLED=0과 HTTPS display: 200을 확인합니다. 출석 시작은 펌웨어 컴파일/업로드를 끝낸 뒤 수행합니다.
팀장 POST /api/posts/P/attendance-sessions에 실제 D를 입력합니다(아래 1은 예시).

```json
{"device_id":1}
```

201의 id를 S0로 기록합니다. OPEN, display_ack=false, 시작~만료 5분이어야 합니다.
일반 회차 응답에는 code가 없어야 합니다.
다음 기기 조회에서 Serial에 Received attendance code: 000047처럼 실제 6자리가 나와야 합니다.
팀장 GET /api/posts/P/attendance-sessions → S0의 display_ack=false입니다. Serial만으로는 LCD ACK를 보내지 않습니다.
GET /api/devices/D/display(DeviceKey=K) → Serial과 같은 code를 확인할 수 있습니다.

선택적인 ACK API 단독 테스트: LCD가 켜져 있지 않은 이 S0에서만 Swagger POST /api/devices/D/ack에 {"session_id":실제S0}를 전송합니다.
200, display_ack=true가 됩니다. 이는 **API 모의 테스트이며 실제 LCD 출력의 증거가 아닙니다**.
다음 S1에서는 수동 ACK를 보내지 않고 ESP32의 자동 ACK만 확인합니다.

팀장 POST /api/attendance-sessions/S0/close → 200/CLOSED.
장치 display → session=null. Serial → IDLE. 다음 회차 전에 반드시 종료합니다.

## 9. LCD 활성화와 실제 출석 회차 (S1)

config.h의 LCD_ENABLED를 1로 바꾸고 다시 업로드합니다. 업로드 후 다음을 확인합니다.

```text
LCD ready: 16x2, SDA=21, SCL=22, address=0x27
```

주소는 실제 자동 탐지 값에 따라 다릅니다. 대기 LCD는 Attendance / Waiting...입니다.
팀장이 POST /api/posts/P/attendance-sessions로 새 회차를 시작하고 id를 S1로 기록합니다.
LCD와 Serial의 실제 코드가 같은지 확인합니다.

```text
Attendance code
Code: 000047
```

Serial: LCD code written; queuing display ACK. → HTTPS ACK: 200.
팀장 GET /api/posts/P/attendance-sessions → S1의 display_ack=true.
GET /api/posts/P/devices → D의 last_ack가 시각으로 갱신됨.
**S1에서는 Swagger 수동 ACK를 보내지 않습니다.**
같은 팀에서 출석 시작을 다시 요청하면 409입니다.
팀장 GET /api/attendance-sessions/S1/records → 팀원 항목, record=null(아직 미출석).

## 10. 팀원: LCD 코드를 입력하여 출석

시크릿 창에서 GET /api/users/me로 팀원인지 확인합니다.
GET /api/posts/P/attendance-sessions → S1과 my_record=null. 일반 사용자 응답에는 code가 없습니다.
POST /api/attendance-sessions/S1/check-in:

```json
{"code":"000047"}
```

예시를 **LCD의 실제 코드**로 바꾸고 반드시 문자열로 보냅니다. 5분 안에 실행합니다.
200, member_id=e2e_mem_1102, is_present=1, checked_in_at 존재를 확인합니다.
한 번 더 같은 요청 → 같은 기록 id/checked_in_at, 출석 행은 하나입니다.
GET /api/posts/P/attendance-sessions → S1의 my_record에 기록이 들어갑니다.
팀장 창 GET /api/attendance-sessions/S1/records → 팀원의 record.is_present=1.

팀원 GET /api/attendance-sessions/S1/records, POST /api/attendance-sessions/S1/close → 각각 403.
팀장 계정은 체크인 대상이 아니므로 팀장 check-in도 403입니다.
호출 중 만료되었다면 팀장이 새 회차를 시작하고 새 회차 ID/코드로 이 단계를 다시 진행합니다.

## 11. 출석 종료와 자동 만료

팀장 POST /api/attendance-sessions/S1/close → 200/CLOSED. 반복 종료도 200.
ESP32의 다음 조회에서 LCD → Waiting..., 장치 GET display → session=null.
회차 이력과 출석 기록은 유지됩니다.
팀원 S1 check-in → 409. 장치 S1 ACK → 409.

자동 만료는 새 S2로 따로 확인합니다. 팀장 POST /api/posts/P/attendance-sessions로 시작하고 id를 S2로 기록합니다.
아무도 인증/종료하지 않고 시작 시점부터 5분이 지나도록 기다립니다.
ESP32가 대기 화면으로 돌아가고 회차 목록 조회는 S2 CLOSED, 장치 display는 session=null이어야 합니다.
팀원 S2 check-in → 409. S1의 기존 출석 기록은 그대로 남아야 합니다.
요청이 전혀 없으면 DB status 정리는 다음 조회 때 수행될 수 있습니다. 서버는 expiry_time으로도 만료를 판정합니다.

선택: 새 회차에서 코드를 받은 뒤 Wi-Fi를 끊어도 로컬 만료에 맞춰 코드가 지워지는지 확인합니다.
오프라인 중 서버의 수동 종료를 즉시 수신할 수는 없습니다. 재연결하면 상태를 다시 받습니다.

## 12. TiDB에서 실제 저장 결과 확인

아래 0을 실제 P/Q/D/S1/S2 숫자로 바꾼 다음 묶음 전체를 실행합니다. SELECT만 수행합니다.
사용자명을 변경했다면 IN 안의 값도 바꿉니다. 세션 만료 확인 API를 먼저 호출합니다.

```sql
USE recruitment_db;
SET @p = 0;
SET @q = 0;
SET @d = 0;
SET @s1 = 0;
SET @s2 = 0;

SELECT username, name, password LIKE '$argon2%' AS password_hashed
FROM Users WHERE username IN ('e2e_lead_1102', 'e2e_mem_1102');

SELECT id, title, current_size, target_size, status
FROM Posts WHERE id IN (@p, @q);

SELECT id, post_id, applicant_id, status
FROM Applications WHERE post_id IN (@p, @q);

SELECT post_id, member_id, application_id
FROM ApprovedMembers WHERE post_id IN (@p, @q);

SELECT id, post_id, last_ack, device_credential LIKE 'sha256:%' AS credential_hashed
FROM Devices WHERE id = @d;

SELECT id, post_id, device_id, status, display_ack, start_time, expiry_time,
       TIMESTAMPDIFF(SECOND, start_time, expiry_time) AS duration_seconds
FROM AttendanceSessions WHERE id IN (@s1, @s2);

SELECT id, session_id, member_id, is_present, checked_in_at
FROM AttendanceRecords WHERE session_id IN (@s1, @s2);

SELECT session_id, member_id, COUNT(*) AS duplicate_count
FROM AttendanceRecords WHERE session_id IN (@s1, @s2)
GROUP BY session_id, member_id HAVING COUNT(*) > 1;

SELECT id, username, revoked_at, expires_at
FROM AuthSessions WHERE username IN ('e2e_lead_1102', 'e2e_mem_1102');
```

기대 결과:

- Users: 두 계정, password_hashed=1. 평문 비밀번호는 출력하지 않습니다.
- P: 2/2 CLOSED, Q: 1/3 CLOSED.
- Applications: P APPROVED, Q REJECTED. ApprovedMembers에는 P의 팀원 한 행만 있습니다.
- Devices: credential_hashed=1, last_ack에 시각 존재. 키 원문/해시 자체는 표시하지 않습니다.
- S1/S2: CLOSED, duration_seconds=300. S1은 display_ack=1입니다.
- AttendanceRecords: S1의 팀원 한 행(is_present=1), 미인증 S2는 0행. 중복 검사는 0행입니다.
- AuthSessions: 로그인 세션을 확인합니다. 다시 로그인한 횟수에 따라 행 수가 늘어납니다.

## 13. 거절·수동 마감용 Q 삭제

DB에서 REJECTED 확인 후 팀장으로 DELETE /api/posts/Q → 200, 삭제 메시지를 확인합니다.
GET /api/posts/Q → 404. 팀원의 내 지원 목록에서 Q 지원이 사라집니다.
TiDB에서 Posts/Applications/ApprovedMembers의 위 SELECT를 다시 실행하여 Q 관련 행이 없는지 확인합니다.
실제로 사용 중인 다른 모집글 ID를 지정하지 않습니다.

P를 삭제하면 D·출석 회차·출석 기록도 CASCADE 삭제됩니다. 프론트 연결용으로 남기려면 P는 삭제하지 않습니다.
CASCADE도 검증할 경우에만 전체 기록 확인 후 P를 DELETE하고 Devices/AttendanceSessions/AttendanceRecords가 사라졌는지 위 SQL로 확인합니다.
이후 ESP32는 삭제된 D에 대해 401이므로 새 장치를 등록하기 전까지 꺼 두어도 됩니다. 사용자 계정은 남습니다.

## 14. 토큰 갱신과 서버 로그아웃 (두 계정에서 마지막에 실행)

각 브라우저 창에서 마지막으로 저장한 본인의 refresh_token을 POST /api/auth/refresh로 보냅니다.

```json
{"refresh_token":"본인의 현재 refresh_token"}
```

200 후 access_token/refresh_token을 둘 다 새 값으로 교체하고 HTTPBearer도 새 access_token으로 바꿉니다.
GET /api/users/me → 200, 본인 정보를 확인합니다. 옛 refresh_token은 다시 보내지 않습니다. 재사용하면 해당 로그인 세션 자체가 무효화됩니다.

POST /api/auth/logout은 선택 본문을 보내지 않는 상태로 실행합니다. Swagger에서 JSON을 전송한다면 아래 대체 방법을 사용합니다.
200과 로그아웃 메시지를 확인한 뒤 **Swagger의 HTTPBearer를 그대로 두고** GET /api/users/me를 다시 실행 → 401입니다.
현재 refresh_token으로 refresh해도 401입니다. 서버 측 세션 무효화를 확인한 것입니다.
두 계정 모두 실행한 뒤 TiDB AuthSessions의 revoked_at에 시각이 들어갔는지 확인합니다.

대체 로그아웃 방법: HTTPBearer를 해제하고 POST /api/auth/logout에 본인의 현재 refresh_token을 보냅니다.

```json
{"refresh_token":"본인의 현재 refresh_token"}
```

## 15. 추가 오류 테스트 (정상 흐름 이후·새 회차 사용)

| 조건 | 기대 |
|---|---|
| 틀린 비밀번호로 login | 401 |
| 비밀번호 7자로 signup | 422 |
| HTTPBearer 없이 POST /api/posts | 401 |
| PATCH /api/posts/P에 빈 JSON | 422 |
| CLOSED인 P에 새 지원 | 409 (같은 팀원은 중복 지원이어도 409) |
| DeviceKey 미설정/잘못된 값으로 display | 401 |
| 유효한 새 회차에 다른 6자리 문자열로 check-in | 400 |
| code="123" 또는 code를 숫자로 전송 | 422 |
| 유효한 새 회차에서 같은 팀원이 1분 내 6회 check-in | 여섯 번째 429, Retry-After 존재 |

시도 제한에는 성공·중복 요청도 포함됩니다. 정상 흐름 중에 너무 많이 반복하지 말고 별도 회차에서 검증합니다.
새 회차에는 새 ID/코드를 사용하고 로그아웃 후라면 다시 로그인해서 실행합니다.

## 완료 판정

전체 28개 API의 정상 흐름과 계정 전환·권한·중복 지원·자동/수동 마감·출석 중복 방지·만료·DB 저장을 확인합니다.
실기기 ACK는 S1의 'LCD에 실제 표시 + 자동 ACK + DB 갱신'으로 판정합니다. Swagger 수동 ACK는 별도 모의 테스트입니다.
이 단계는 Swagger/ESP32/TiDB 통합 확인이며, 프론트의 실제 화면 연결은 이후 같은 흐름으로 따로 확인합니다.
