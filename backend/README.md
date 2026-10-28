# 모집 프로젝트 백엔드

Python 3.12 + FastAPI + SQLAlchemy + PyMySQL + MySQL을 사용합니다.
현재 배포 구성은 **Render 웹 서버 + TiDB Cloud Starter(MySQL Compatible)**입니다.
이 문서는 이미 배포된 Render 서버를 기준으로 안내합니다.
PC에서 직접 개발·실행할 때는 [로컬 개발 안내](docs/local-development.md), 새 서버를 구성할 때는 [Render + TiDB 단계별 안내](docs/render-tidb.md)를 참고하세요.
현재 서버/DB 상태 확인, 회원가입, 로그인/갱신/로그아웃, 내 정보, 모집글 조회/작성/수정/삭제/마감,
지원/지원자 조회/승인·거절/내 지원/내 팀을 제공합니다. API 버전은 0.3.0입니다.
새 지원 API와 DB 변경/Swagger 테스트 순서는 [지원·승인·내 활동 안내](docs/applications-and-activities.md)를 확인하세요.
추가 API의 요청/응답과 프론트 연결 방법은 [계정·모집글 API 안내](docs/accounts-and-posts.md)를 확인하세요.
**기존 DB에 001·002 변경을 적용하고 확인까지 마쳤다면, SQL 재실행 없이 코드를 push·배포하면 됩니다.**
현재 연결된 TiDB에는 001·002 변경 적용이 완료되었습니다(사용자 확인). 같은 DB에서는 다시 실행하지 않습니다.

DB 변경을 아직 적용하지 않은 환경에서만 아래 순서를 따릅니다.

- AuthSessions가 없으면 [001 SQL](migrations/001_auth_sessions.sql)로 테이블을 추가합니다.
- 지원 관련 고유 제약을 아직 추가하지 않았다면 [002 사전 점검](migrations/002_applications_precheck.sql) 후
  [002 변경 SQL](migrations/002_applications_unique.sql)을 한 번 적용하고 [적용 확인](migrations/002_applications_verify.sql)을 실행합니다.
- 이 작업은 DB별 최초 적용 안내이며, push·재배포·서버 재시작마다 반복하지 않습니다.
- migrations/의 SQL 파일은 팀원 공유와 새 DB 구성에 필요한 변경 이력으로 보관합니다.

기존 8개 테이블은 유지됩니다. 출석과 ESP32 펌웨어는 다음 단계에서 추가합니다.

## 파일별 역할

| 파일 | 내용 |
| --- | --- |
| `app/main.py` | 앱 생성, 라우터 등록, CORS, 안전한 오류 응답 |
| `app/config.py` | `.env` 및 서버 환경변수 읽기 |
| `app/database.py` | MySQL 연결, 요청별 DB 세션 |
| `app/models.py` | Users/Posts, 정원·내 지원 조회용 Applications/ApprovedMembers, AuthSessions 매핑 |
| `app/schemas.py` | 입력 검증, 비밀번호가 없는 응답 모델 |
| `app/security.py` | Argon2 비밀번호 해시, JWT 생성/검증 |
| `app/dependencies.py` | DB 세션과 로그인 사용자 조회 |
| `app/routers/health.py` | 서버/DB 상태 확인 |
| `app/routers/auth.py` | 회원가입, 로그인, 토큰 갱신, 서버 로그아웃, 내 정보 |
| `app/routers/posts.py` | 공개 조회, 작성자 전용 작성/수정/삭제/마감, 내 상태 조회 |
| `app/routers/applications.py` | 지원/승인·거절/내 활동 API 5개 |
| `app/services/recruitment.py` | 모집글 잠금·작성자 검사·승인 인원 계산 공통 규칙 |
| `migrations/001_auth_sessions.sql` | 기존 데이터 보존하며 로그인 세션 테이블 추가 |
| `scripts/init_env.py` | 기존 파일을 덮어쓰지 않고 `.env` 생성 |
| `scripts/hash_seed_passwords.py` | SQL 테스트 계정의 평문 비밀번호를 해시로 변환 |
| `requirements.txt` | 실행 라이브러리 |
| `requirements-dev.txt` | 테스트 라이브러리 |
| `requirements.lock.txt` | 검증한 실행 환경의 정확한 버전 |
| `requirements-dev.lock.txt` | 검증한 실행/테스트 환경의 정확한 버전 |
| `tests/` | SQLite 독립 API 테스트와 선택형 로컬 MySQL 검증 |

## 1. 현재 배포 환경

| 항목 | 현재 구성 |
| --- | --- |
| 백엔드 서버 | Render |
| API 기본 주소 | https://swe-project-u3f0.onrender.com |
| DB | TiDB Cloud Starter / MySQL Compatible |
| DB 이름 | recruitment_db |
| GitHub 저장소 | SJ-sw-engineering/SWE-project |
| Render 배포 브랜치 | backend |
| Render Root Directory | backend |

배포 서버의 설정은 Render 서비스의 **Environment**에서 관리합니다.
DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD는 TiDB 연결 정보이며 DB_SSL은 true입니다.
DB_HOST에는 TiDB 호스트를 입력합니다. 위 Render 주소는 프론트에서 API를 호출하는 주소입니다.
JWT_SECRET_KEY는 Render에 등록한 기존 값을 계속 사용합니다.
로컬 PC의 .env를 수정해도 Render의 환경변수는 바뀌지 않습니다.
비밀값은 코드와 GitHub에 넣지 않고 .env.example만 공유합니다.

## 2. 코드 업데이트와 DB 변경

현재 공유 TiDB에는 기존 테이블과 AuthSessions를 포함한 8개 테이블이 있고, 001·002 변경도 적용된 상태입니다.
현재 DB를 사용하는 팀원은 별도로 DB를 초기화하거나 비밀번호 해시 변환을 다시 실행할 필요가 없습니다.
앱은 시작 시 DB를 생성·삭제하거나 초기 데이터를 넣지 않습니다.

코드를 수정한 뒤 다음 순서로 반영합니다.

1. 변경 파일을 commit하고 GitHub backend 브랜치에 push합니다.
2. Render의 배포 브랜치가 backend이고 Auto-Deploy가 On Commit이면 자동 배포가 시작됩니다.
3. 자동 배포가 시작되지 않으면 Manual Deploy > Deploy latest commit을 실행합니다.
4. 최신 커밋 배포가 성공했는지 확인하고 아래 /docs에서 반영된 API를 확인합니다.

DB 변경 SQL이 새로 추가되는 경우에만 해당 버전 안내에 따라 한 번 적용합니다.
기존 원본 SQL의 DROP/INSERT를 재실행하지 않습니다. migrations/ 파일은 새 DB 구성과 변경 이력 공유용으로 보관합니다.
새 개발 DB를 따로 만드는 절차는 [Render + TiDB 안내](docs/render-tidb.md)를 참고하세요.

## 3. Render 서버 접속과 상태 확인

| 용도 | 주소 |
| --- | --- |
| 서버 기본 주소 | https://swe-project-u3f0.onrender.com |
| Swagger API 테스트 | https://swe-project-u3f0.onrender.com/docs |
| API 스키마 / 코드 버전 확인 | https://swe-project-u3f0.onrender.com/openapi.json |
| 서버 상태 확인 | https://swe-project-u3f0.onrender.com/health |
| TiDB 연결 확인 | https://swe-project-u3f0.onrender.com/health/db |
| 모집글 목록 | https://swe-project-u3f0.onrender.com/api/posts |

배포된 서버를 이용하거나 Swagger에서 테스트할 때는 이 주소로 접속합니다.
코드의 현재 API 버전은 0.3.0이며 실제 배포 반영 여부는 /docs 또는 /openapi.json의 버전과 API 목록으로 확인합니다.
Render 무료 서버가 sleep 상태이면 첫 요청에서 시작 시간이 걸릴 수 있습니다.

`/health`는 DB에 연결하지 않으므로 DB가 꺼져 있어도 200을 반환합니다.
`/health/db`는 실제 MySQL에 `SELECT 1`을 실행합니다. DB 문제가 있으면 503을 반환합니다.
서버/로그인 실패 응답에 비밀번호, 접속 정보, SQL 쿼리는 포함하지 않습니다.

## 4. API 계약

| 메서드 | 주소 | 로그인 | 용도 |
| --- | --- | --- | --- |
| GET | `/health` | 불필요 | 서버 실행 확인 |
| GET | `/health/db` | 불필요 | 실제 DB 연결 확인 |
| POST | `/api/auth/signup` | 불필요 | 회원가입 |
| POST | `/api/auth/login` | 불필요 | 학번/비밀번호 로그인 |
| POST | `/api/auth/refresh` | 갱신 토큰 | 토큰 교체/갱신 |
| POST | `/api/auth/logout` | 접근 또는 갱신 토큰 | 현재 로그인 세션 종료 |
| GET | `/api/users/me` | 필요 | 로그인한 사용자 조회 |
| GET | `/api/posts` | 불필요 | 모집글 목록/검색 |
| GET | `/api/posts/{post_id}` | 불필요 | 모집글 상세 |
| POST | `/api/posts` | 필요 | 모집글 작성 |
| PATCH | `/api/posts/{post_id}` | 작성자 | 모집글 부분 수정 |
| DELETE | `/api/posts/{post_id}` | 작성자 | 모집글과 관련 기록 삭제 |
| POST | `/api/posts/{post_id}/close` | 작성자 | 수동 마감 |
| GET | `/api/posts/{post_id}/context` | 필요 | 팀장 여부와 본인 지원 상태 |
| POST | `/api/posts/{post_id}/applications` | 필요 | 지원 |
| GET | `/api/posts/{post_id}/applications` | 팀장 | 지원자 목록 |
| PATCH | `/api/applications/{application_id}` | 팀장 | 승인/거절 |
| GET | `/api/users/me/applications` | 필요 | 내 지원 현황 |
| GET | `/api/users/me/teams` | 필요 | 내가 만든 팀/승인된 팀 |

### 로그인

`Content-Type: application/json`으로 전송합니다. 학번과 비밀번호는 문자열입니다.
Swagger의 `/api/auth/login`에서 `Try it out`을 눌러 다음 값을 넣을 수 있습니다.
해시 변환 후 원본 SQL의 첫 테스트 계정으로 로그인할 수 있습니다.

```json
{"username": "20191001", "password": "20000115"}
```

응답 예시:

```json
{
  "access_token": "발급된 JWT",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token": "발급된 갱신 토큰",
  "refresh_expires_in": 1209599,
  "user": {"username": "20191001", "name": "학생1", "created_at": "2026-10-06T00:00:00Z"}
}
```

이 응답의 토큰을 Swagger 상단 `Authorize`에 넣으세요. 토큰 문자열만 입력하면 됩니다.
프론트엔드에서는 보호된 API 요청에 `Authorization: Bearer 발급된토큰` 헤더를 붙입니다.
접근 토큰은 기본 30분, 로그인 세션과 갱신 토큰은 기본 14일입니다.
갱신할 때마다 refresh_token을 교체하며, 최초 로그인 시점의 14일 제한은 연장하지 않습니다.
서버 로그아웃 후에는 해당 세션에서 발급한 접근/갱신 토큰이 모두 거부됩니다.
같은 계정으로 다른 탭/기기에서 따로 로그인한 세션은 유지됩니다.
이 버전 이전의 세션 ID 없는 JWT는 다시 로그인해야 합니다.

PowerShell에서도 배포 서버의 로그인과 내 정보 조회를 확인할 수 있습니다.

```powershell
$apiBaseUrl = 'https://swe-project-u3f0.onrender.com'
$loginBody = @{ username = '20191001'; password = '20000115' } | ConvertTo-Json
$loginResult = Invoke-RestMethod -Method Post -Uri "$apiBaseUrl/api/auth/login" -ContentType 'application/json' -Body $loginBody
$authHeaders = @{ Authorization = "Bearer $($loginResult.access_token)" }
Invoke-RestMethod -Uri "$apiBaseUrl/api/users/me" -Headers $authHeaders
```

### 모집글 목록

```text
GET /api/posts?page=1&page_size=20
GET /api/posts?keyword=파이썬
GET /api/posts?category=Web%2FFrontend&status=RECRUITING
```

- `page`: 1부터 시작
- `page_size`: 1~100, 기본 20
- `keyword`: 제목 또는 내용에 포함된 문자열
- `category`: 카테고리 정확히 일치
- `status`: `RECRUITING` 또는 `CLOSED`
- 최신 작성 시간, ID 내림차순 정렬
- 목록의 `items`에는 본문이 없고, 상세 응답에는 `content`가 추가됩니다.
- 공개 응답에는 작성자 이름만 제공합니다. 학번과 비밀번호는 포함하지 않습니다.

```json
{
  "items": [{
    "id": 1, "author_name": "학생1", "title": "모집글 제목",
    "category": "Web/Frontend", "target_size": 4, "current_size": 2,
    "status": "RECRUITING", "created_at": "2026-10-06T00:00:00Z"
  }],
  "total": 5,
  "page": 1,
  "page_size": 20
}
```

오류는 `{ "detail": ... }` 형식입니다.
401: 로그인 실패/토큰 오류, 403: 작성자 권한 없음, 404: 없는 모집글,
409: 아이디 중복/현재 인원보다 작은 정원, 422: 입력 오류, 503: DB 처리 실패.
잘못된 로그인은 존재하지 않는 계정과 잘못된 비밀번호에 같은 응답을 제공합니다.

## 5. 팀원과 연결

프론트엔드의 API 기본 주소는 `https://swe-project-u3f0.onrender.com`으로 설정합니다.
프론트는 본인 PC에서 실행하더라도 배포된 Render API를 호출할 수 있습니다. 주소는 설정 한 곳에서 관리합니다.
프론트엔드 주소가 바뀌면 Render Environment의 `CORS_ORIGINS`에 허용할 주소를 JSON 배열로 등록하고 설정을 반영해 재배포합니다.
예: `["http://localhost:5500","http://127.0.0.1:5500","https://실제프론트주소"]`.
PC의 .env는 로컬 백엔드 실행용입니다. 자세한 사용법은 [로컬 개발 안내](docs/local-development.md)를 참고하세요.
같은 GitHub 저장소에서는 이 폴더를 루트의 `backend/`로 넣고 본인 작업 브랜치에서 작업하면 됩니다.
공유할 내용은 이 README와 `/docs` 또는 `/openapi.json`입니다.
DB 스키마 변경은 DB 담당자와 합의한 SQL 변경 파일로 진행하세요.

### Git에 포함할 파일

현재 작업공간 루트에서 저장소를 초기화할 경우, 루트 `.gitignore`는 동기화 참조 자료 `sources/`,
로컬 `AGENTS.md`, 임시 검증 자료 `tmp/`, 압축 결과 `output/`을 제외합니다.
루트와 backend의 `.gitignore` 모두 `.env`, 가상환경, 인증 키, 일반적인 클라우드 자격 증명 파일을 제외합니다.
코드, README, requirements/lock 파일, `.env.example`, 개인정보 없는 스키마/변경 SQL은 공유합니다.
`.sql` 전체를 제외하지 않으므로 실제 개인정보가 있는 INSERT 데이터나 DB 덤프는 직접 확인해야 합니다.
Git 초기화 후 `git status --short`와 `git diff --cached --name-only`로 실제 포함 파일을 확인하세요.
이미 추적된 비밀 파일에는 `.gitignore`가 소급 적용되지 않습니다. 이 경우 추적 해제와 노출된 키 교체가 필요합니다.
새 프로젝트 폴더로 backend만 옮기는 경우에도 backend의 `.gitignore`를 함께 옮기세요.

## 6. 테스트

배포 API 테스트는 [Render Swagger](https://swe-project-u3f0.onrender.com/docs)에서 진행합니다.

- 회원가입·로그인·갱신·로그아웃·모집글 관리: [계정·모집글 API 안내](docs/accounts-and-posts.md)
- 지원·승인·내 활동 및 실제 TiDB 조회 결과 대조: [지원·승인·내 활동 안내](docs/applications-and-activities.md)
- PC에서 자동 테스트 실행: [로컬 개발 안내](docs/local-development.md)

일반 자동 테스트는 독립적인 메모리 SQLite를 사용하며 공유 TiDB는 읽거나 수정하지 않습니다.
2026-10-28 버전은 SQLite 독립 테스트 **81개**, 별도 로컬 MySQL 테스트 **4개 통과**를 확인했습니다.
일반 pytest 실행 시 MySQL 테스트 4개는 전용 로컬 DB 환경변수가 없으면 skip됩니다.
회원가입, 토큰 교체/로그아웃,
작성자 권한, 현재 승인 인원에 따른 정원 검증, 연관 데이터 삭제, CORS와 기존 API를 포함합니다.
로그인/토큰 검증, 비밀값 비노출, DB 오류 처리, 검색/필터/페이지, 비밀번호 변환의 재실행을 확인합니다.
자동 테스트와 별개로 Render의 `/health/db`에서 실제 TiDB 연결을 확인합니다.
검증 시 정확한 패키지 버전은 lock 파일에 기록합니다. 범위 기반 requirements는 향후 업데이트 검토용입니다.

이전 1단계 검증 기록: 독립 테스트 23개 통과. 별도의 임시 MySQL 8.4에서 첨부 SQL의 7개 테이블,
70개 계정 해시 변환, 로그인/내 정보/한글 검색/필터/페이지/상세 조회를 확인했습니다.
2026-10-07 수정본 `recruitment_db (1).sql`도 임시 MySQL 8.4에서 검증했습니다.
승인 팀원 2명과 모집글별 재계산 인원(2, 1, 1, 1, 2)이 API에 반영되며 기존 테스트 23개도 통과합니다.
실제 개발 DB는 접속 정보 설정 후 별도로 확인해야 합니다.
테스트 도구에는 httpx 관련 향후 전환 안내 경고 1개가 있으며 테스트 결과에는 영향을 주지 않습니다.

## 다음 구현 순서

1. 프론트 서버 모드에 계정/모집글 관리/지원·내 활동 API 연결
2. 5분 출석 세션, 6자리 문자열 코드, 회원 출석 입력, 중복 방지
3. ESP32 인증/코드 조회/표시 완료 확인과 LCD 연동

출석 코드는 일반 팀원 조회 응답에 포함하지 않고 인증된 기기 API에서만 전달하는 계획입니다.
최신 SQL에서 승인 팀원 등록과 현재 인원 재계산은 반영되었습니다.
002 SQL은 승인 멤버 기준으로 인원을 보정하고 2/2인데 RECRUITING인 5번 샘플도 CLOSED로 맞춥니다.
3번 글은 1/3명으로 재계산되어도 `CLOSED`가 유지되며, 이는 수동 마감으로 허용할 수 있습니다.
중복 지원/팀원 등록 UNIQUE 제약은 002 SQL로 적용합니다. 기술 스택 프로필 구조는 추가하지 않았습니다.
변경 비교는 `docs/db-update-2026-10-07.md`를 참고하세요.
