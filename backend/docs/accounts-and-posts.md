# 회원가입·토큰 관리·모집글 관리 API

2026-10-26 구현. 기존 로그인/공개 모집글 조회 경로와 필드는 유지합니다.
프론트 브랜치의 화면/어댑터 변경, 실제 TiDB SQL 실행, GitHub push와 Render 배포는 이번 코드 작성에 포함되지 않습니다.

## 배포 전 DB 변경

서버 로그아웃 상태를 재시작 후에도 유지하기 위해 AuthSessions 테이블 하나를 추가합니다.
기존 일곱 테이블은 유지되고 총 여덟 테이블이 됩니다. Users/Posts 컬럼은 바뀌지 않습니다.

1. TiDB SQL Editor에서 현재 데이터가 있는 `recruitment_db`를 선택합니다.
2. `backend/migrations/001_auth_sessions.sql`의 전체 CREATE TABLE 문을 실행합니다.
3. `SHOW TABLES FROM recruitment_db;`로 AuthSessions가 생겼는지 확인합니다.
4. 코드 반영 후 Render를 배포합니다. 기존 DB_*와 JWT_SECRET_KEY는 그대로 사용합니다.
5. `/docs`에서 새로 로그인하여 API를 확인합니다.

기존 사용자가 있으므로 원본 전체 SQL의 DROP/INSERT를 다시 실행하지 않습니다.
앱은 시작할 때 스키마를 자동으로 변경하지 않습니다. 이 SQL이 없으면 새 로그인 등이 503으로 실패할 수 있습니다.
이전 버전의 세션 ID 없는 JWT는 새 배포 후 401이므로 한 번 다시 로그인합니다.
선택 환경변수 `REFRESH_TOKEN_EXPIRE_DAYS=14`는 생략해도 기본 14일입니다.

## 공통 규칙

- JSON 요청/응답을 사용합니다. 삭제/로그아웃 성공도 빈 응답이 아닌 JSON입니다.
- 보호된 API는 `Authorization: Bearer <access_token>` 헤더를 받습니다.
- refresh_token은 인증 헤더에 넣는 접근 토큰이 아닙니다.
- 시간은 UTC이며 응답의 created_at은 Z로 끝납니다.
- 오류는 `{ "detail": "안내" }`, 입력 오류는 `{ "detail": [{ "loc": [], "msg": "...", "type": "..." }] }`입니다.
- 401 인증 실패, 403 작성자 권한 없음, 404 모집글 없음, 409 중복/정원 충돌, 422 입력 형식, 503 DB 오류입니다.

## 회원가입

`POST /api/auth/signup` → 201

```json
{"username":"student01","name":"홍길동","password":"example-password-123"}
```

- username: 영문/숫자/밑줄/하이픈 4~20자. 숫자 학번도 사용할 수 있습니다.
- name: 앞뒤 공백 제거 후 1~50자.
- password: 8~128자. Argon2 해시로 저장합니다.
- password_check는 브라우저에서만 비교하고 요청에 넣지 않습니다.
- 아이디 중복은 409입니다. DB 고유 키로 동시에 들어온 중복 가입도 차단합니다.
- 성공은 `{ "username": "student01", "name": "홍길동", "created_at": "...Z" }`이며 자동 로그인하지 않습니다.

## 로그인과 갱신

`POST /api/auth/login`의 요청은 기존 username/password와 같습니다.

로그인과 `POST /api/auth/refresh`의 성공 응답은 같은 형태입니다.

```json
{
  "access_token": "JWT 접근 토큰",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token": "JWT 갱신 토큰",
  "refresh_expires_in": 1209599,
  "user": {"username":"student01","name":"홍길동","created_at":"...Z"}
}
```

expires_in/refresh_expires_in은 응답을 만든 시점의 남은 초입니다.
접근 토큰은 기본 30분, 갱신 토큰은 최초 로그인부터 최대 14일입니다. 세션 만료 직전에는 접근 토큰도 남은 세션 시간까지만 발급합니다.
서버는 갱신 토큰의 SHA-256 해시만 DB에 저장하고 원문은 저장하지 않습니다.

접근 토큰이 만료되면 Bearer 헤더 없이 다음 JSON을 전송할 수 있습니다.

```text
POST /api/auth/refresh
Content-Type: application/json
```

```json
{"refresh_token":"현재 저장한 갱신 토큰"}
```

- 성공하면 접근 토큰과 갱신 토큰을 **둘 다** 새 응답으로 교체합니다.
- 이미 교체한 이전 갱신 토큰을 재사용하면 401이고 해당 로그인 세션을 폐기합니다. 다른 로그인 세션에는 영향이 없습니다.
- 변조된 토큰이나 접근 토큰을 갱신 입력에 넣으면 401입니다.
- 프론트는 동시에 여러 요청이 401을 받아도 갱신 요청을 한 번만 실행하고, 그 결과를 함께 사용해야 합니다.
- 갱신에 실패하거나 결과를 잃어버렸다면 같은 옛 토큰을 반복 전송하지 말고 재로그인을 안내합니다.
- 최초 로그인부터 14일이 지나면 다시 로그인해야 합니다. 사용하지 않는 DB 세션의 정기 삭제 기능은 이번 범위에 포함하지 않았습니다.

## 서버 로그아웃

방법 A: 유효한 접근 토큰이 있으면 본문 없이 호출합니다.

```text
POST /api/auth/logout
Authorization: Bearer <access_token>
```

방법 B: 접근 토큰이 만료되었으면 Bearer 없이 갱신 토큰을 보냅니다.

```text
POST /api/auth/logout
Content-Type: application/json
```

```json
{"refresh_token":"현재 저장한 갱신 토큰"}
```

성공: 200 `{ "detail": "로그아웃되었습니다." }`.
두 방법을 함께 보내면 본문의 갱신 토큰을 기준으로 처리합니다.
같은 유효 기간 내의 발급된 토큰으로 로그아웃을 반복 호출해도 200입니다.
성공 직후 해당 세션의 기존 접근 토큰으로 보호 API를 호출하거나 갱신 토큰을 사용하면 401입니다.
서버 재시작 후에도 취소 상태를 유지하며, 같은 계정의 다른 로그인 세션은 유지됩니다.
유효한 토큰이 없는 요청은 401입니다.

프론트는 서버 요청을 먼저 수행하고 저장한 토큰/사용자 정보를 지웁니다.
현재 프론트의 logout은 브라우저 데이터만 지우므로 별도로 이 API를 연결해야 합니다.
토큰은 HTTPS로 전송하고 비밀번호/토큰을 로그에 출력하거나 저장소에 커밋하지 않습니다.

## 모집글 작성

`POST /api/posts` + Bearer → 201 PostDetail

```json
{"title":"팀원 모집","content":"함께 프로젝트를 진행합니다.","category":"Web/Frontend","target_size":4}
```

- title: 공백 제거 후 1~255자.
- content: 공백 제거 후 1~10000자.
- category: 공백 제거 후 1~100자.
- target_size: 팀장 포함 2~100의 정수.
- author_id는 토큰에서 결정합니다. author_id/current_size/status를 요청에 넣으면 422입니다.
- 생성 시 current_size=1, status=RECRUITING입니다.
- 성공 응답은 기존 상세 응답과 같은 필드(id/author_name/title/content/category/target_size/current_size/status/created_at)입니다.

## 수정·삭제·마감

| 메서드/경로 | 요청 | 성공 |
| --- | --- | --- |
| PATCH /api/posts/{id} | 수정할 title/content/category/target_size | 200 PostDetail |
| DELETE /api/posts/{id} | 본문 없음 | 200 `{ "detail": "모집글이 삭제되었습니다." }` |
| POST /api/posts/{id}/close | 본문 없음 | 200 PostDetail |

세 API 모두 로그인한 작성자만 사용할 수 있습니다. 다른 사용자는 403입니다.
PATCH는 적어도 한 필드가 있어야 하고 null/빈 문자열은 허용하지 않습니다.
팀 정원은 팀장 1명 + 실제 ApprovedMembers 수보다 작게 줄일 수 없습니다(409).
수정/마감 시 승인 팀원을 기준으로 current_size를 맞춥니다. 정원 도달 시 CLOSED로 처리합니다.
정원을 늘리거나 내용을 수정해도 CLOSED 글을 자동으로 다시 모집하지 않습니다.
이미 마감한 글의 /close 반복 호출은 200입니다.
삭제하면 기존 DB의 ON DELETE CASCADE에 따라 지원·승인 팀원·장치·출석 회차/기록도 삭제됩니다.
글이 없거나 이미 삭제한 글을 다시 삭제하면 404입니다.

## 로그인한 사용자의 모집글 상태

`GET /api/posts/{id}/context` + Bearer

```json
{"is_owner":true,"my_application":null}
```

이미 지원했다면 my_application은 `{ "id": 1, "status": "PENDING" }`와 같은 형태입니다.
공개 모집글에 작성자 학번이나 다른 사람의 지원 내용을 추가하지 않습니다.
프론트는 기존 상세 조회와 이 응답을 조합하고, author_id 비교 대신 is_owner로 수정/삭제 버튼을 표시합니다.
이 응답은 권한 표시용이며 백엔드는 실제 수정 요청에서도 작성자를 검사합니다.
지원 생성/승인 API는 아직 없고 기존 DB에 들어 있는 본인 지원 정보만 조회합니다.

## 프론트 담당자 연결 목록

1. server.js에서 signup/savePost/deletePost/closePost와 refresh/logout 요청을 추가합니다.
2. savePost는 서버 응답 객체의 id를 반환하도록 맞추면 기존 화면 이동 코드를 재사용할 수 있습니다.
3. target_size는 Number로 변환하고 password_check는 가입 요청에서 제외합니다.
4. refresh_token, refresh_expires_in도 현재 로그인 세션과 함께 보관하고 갱신 성공 시 함께 교체합니다. 비밀번호는 저장하지 않습니다.
5. 현재 프론트 auth()는 접근 토큰 만료 시 로그인 데이터를 지웁니다. 만료 시 갱신할 기회를 주도록 이 처리도 바꿔야 합니다.
6. 공통 요청의 401 처리는 갱신을 시도한 뒤 실패할 때 로그아웃하도록 수정합니다. refresh/login 요청 자체는 무한 재시도하지 않습니다.
7. logout이 비동기 API가 되므로 메뉴 이벤트에서 완료를 기다린 후 화면을 이동합니다.
8. app.js 서버 모드 페이지 제한, 메뉴, serverDetail 화면을 기능별로 열고 context 정보를 연결합니다.
9. 403/409 오류 안내를 추가합니다. 모든 성공 응답이 JSON이므로 기존 응답 파서는 사용할 수 있습니다.
10. 프론트의 실제 배포 주소를 Render CORS_ORIGINS에 등록합니다. PATCH/DELETE는 백엔드에 허용했습니다.

## 검증

테스트는 실제 TiDB와 분리된 SQLite를 사용하며 외래 키를 활성화합니다.
2026-10-26 실행 결과: **60 passed**. 기존 httpx 관련 향후 전환 안내 경고 1개가 있으며 실패는 없습니다.
회원가입/비밀번호 해시/중복/입력 검증, 토큰 교체/재사용 차단/종류 구분/만료/로그아웃 지속성,
작성자 권한/부분 수정/정원/자동·수동 마감/삭제와 연관 데이터 정리/CORS 및 기존 조회를 검증합니다.
실제 TiDB의 SQL 적용과 Render/프론트 통합 동작은 배포 후 별도로 확인합니다.

참고: 갱신 토큰 교체와 재사용 감지는 [RFC 9700의 Refresh Token Protection](https://www.rfc-editor.org/rfc/rfc9700.html#section-4.14.2)을 참고했습니다.
