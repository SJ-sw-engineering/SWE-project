# 모집 프로젝트 백엔드

Python 3.12 + FastAPI + SQLAlchemy + PyMySQL + MySQL을 사용합니다.
현재 배포 구성은 **Render 웹 서버 + TiDB Cloud Starter(MySQL Compatible)**입니다.
처음 연결할 때는 [Render + TiDB 단계별 안내](docs/render-tidb.md)를 따르세요.
현재 서버/DB 상태 확인, 회원가입, 로그인/갱신/로그아웃, 내 정보, 모집글 조회/작성/수정/삭제/마감을 제공합니다.
추가 API의 요청/응답과 프론트 연결 방법은 [계정·모집글 API 안내](docs/accounts-and-posts.md)를 확인하세요.
**이번 버전을 배포하기 전에 [AuthSessions 추가 SQL](migrations/001_auth_sessions.sql)을 기존 recruitment_db에 실행해야 합니다.**
지원/승인 처리 API, 출석, ESP32 펌웨어는 다음 단계에서 추가합니다.

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
| `migrations/001_auth_sessions.sql` | 기존 데이터 보존하며 로그인 세션 테이블 추가 |
| `scripts/init_env.py` | 기존 파일을 덮어쓰지 않고 `.env` 생성 |
| `scripts/hash_seed_passwords.py` | SQL 테스트 계정의 평문 비밀번호를 해시로 변환 |
| `requirements.txt` | 실행 라이브러리 |
| `requirements-dev.txt` | 테스트 라이브러리 |
| `requirements.lock.txt` | 검증한 실행 환경의 정확한 버전 |
| `requirements-dev.lock.txt` | 검증한 실행/테스트 환경의 정확한 버전 |
| `tests/` | 실제 MySQL을 사용하지 않는 독립 API 테스트 |

## 1. 설치

아래 명령은 **backend 폴더에서**, Windows PowerShell로 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m scripts.init_env
```

가상환경을 활성화하지 않아도 위처럼 실행할 수 있습니다.
`.env`를 열고 본인의 `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`를 설정하세요.
JWT 서명 키는 자동 생성되므로 직접 공유하거나 GitHub에 올리지 마세요.
`.env.example`만 GitHub에 올립니다.
서버 환경변수는 `.env`보다 우선합니다.

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=recruitment_db
DB_USER=recruitment_app
DB_PASSWORD="본인의 DB 비밀번호"
DB_SSL=false
```

배포 서버가 정해지면 같은 환경변수를 해당 서버에 등록하면 됩니다.
TiDB Cloud에서는 Connect 화면의 호스트/포트/사용자/DB 비밀번호를 사용하고 `DB_SSL=true`를 설정합니다.
Google 계정 로그인 비밀번호는 DB 비밀번호가 아닙니다.

## 2. MySQL 준비

최신 첨부 SQL `recruitment_db (1).sql`을 DB 담당자가 준비한 **개발용 MySQL**에 먼저 가져와야 합니다.
최신 파일은 기존 `recruitment_db.sql`과 테이블 구조가 같고, 승인 팀원과 현재 인원 샘플을 보완한 버전입니다.
SQL에는 `DROP TABLE`이 있으므로 이미 운영 데이터가 있는 DB에서는 재실행하지 마세요.
이 백엔드는 시작할 때 테이블을 만들거나 삭제하거나 샘플 데이터를 넣지 않습니다.
프로젝트의 기존 일곱 테이블을 준비한 후 `migrations/001_auth_sessions.sql`로 AuthSessions를 추가합니다.
이미 TiDB에 사용자/모집글이 있다면 원본 SQL을 다시 실행하지 말고 추가 SQL만 실행합니다.
서버 재시작이나 새 배포 때마다 SQL을 다시 실행할 필요는 없습니다.
대소문자까지 원본 테이블명과 일치해야 합니다.

원본 SQL에는 생년월일 8자리 평문 비밀번호가 있습니다. API는 평문 비밀번호를 DB 값과 직접 비교하지 않습니다.
SQL 파일을 가져올 때 문자셋은 UTF-8/utf8mb4로 지정하세요. MySQL CLI라면 `--default-character-set=utf8mb4`를 사용합니다.
로그인 전에 다음 명령으로 테스트 계정의 DB 값을 Argon2 해시로 바꾸세요.

```powershell
# 변경 없이 변환 대상 수 확인
.\.venv\Scripts\python.exe -m scripts.hash_seed_passwords

# 명시적으로 실제 DB에 반영
.\.venv\Scripts\python.exe -m scripts.hash_seed_passwords --apply
```

`Users.password` 컬럼명은 유지합니다. 로그인할 때 입력하는 비밀번호도 그대로이며, DB 저장값만 바뀝니다.
기존 해시는 그대로 보존하고, 원본 샘플 형식인 8자리 숫자만 변환합니다.
원본 SQL을 다시 가져오면 평문으로 되돌아오므로 다시 변환해야 합니다.
실제 서비스에서는 생년월일을 초기 비밀번호로 사용하는 정책도 변경해야 합니다.
DB 계정은 앱에 필요한 권한만 부여하고, 스키마 생성/변경은 별도 관리 계정으로 진행하세요.
앱은 MySQL 연결의 시간대를 UTC로 설정합니다. API의 `created_at`은 UTC 기준입니다.

## 3. 실행과 상태 확인

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- 서버: http://127.0.0.1:8000
- API 문서: http://127.0.0.1:8000/docs
- 서버 확인: http://127.0.0.1:8000/health
- DB 확인: http://127.0.0.1:8000/health/db

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

PowerShell에서도 전체 흐름을 확인할 수 있습니다.

```powershell
$loginBody = @{ username = '20191001'; password = '20000115' } | ConvertTo-Json
$loginResult = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/auth/login' -ContentType 'application/json' -Body $loginBody
$authHeaders = @{ Authorization = "Bearer $($loginResult.access_token)" }
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/users/me' -Headers $authHeaders
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

프론트엔드는 백엔드와 별도 프로세스로 실행하고, API 기본 주소를 설정합니다.
프론트엔드에서 `localhost:8000`을 코드 여러 곳에 직접 적지 말고 설정 한 곳에서 관리하세요.
프론트엔드 주소가 바뀌면 `.env`의 `CORS_ORIGINS`를 JSON 배열로 수정하고 서버를 재시작하세요.
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

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock.txt
.\.venv\Scripts\python.exe -m pytest -q
```

테스트는 독립적인 메모리 SQLite를 사용하며 본인의 MySQL은 읽거나 수정하지 않습니다.
2026-10-26 버전은 독립 테스트 **60개 통과**를 확인했습니다. 회원가입, 토큰 교체/로그아웃,
작성자 권한, 현재 승인 인원에 따른 정원 검증, 연관 데이터 삭제, CORS와 기존 API를 포함합니다.
로그인/토큰 검증, 비밀값 비노출, DB 오류 처리, 검색/필터/페이지, 비밀번호 변환의 재실행을 확인합니다.
테스트 통과와 별개로 본인의 MySQL 연결은 `/health/db`에서 확인해야 합니다.
검증 시 정확한 패키지 버전은 lock 파일에 기록합니다. 범위 기반 requirements는 향후 업데이트 검토용입니다.

이전 1단계 검증 기록: 독립 테스트 23개 통과. 별도의 임시 MySQL 8.4에서 첨부 SQL의 7개 테이블,
70개 계정 해시 변환, 로그인/내 정보/한글 검색/필터/페이지/상세 조회를 확인했습니다.
2026-10-07 수정본 `recruitment_db (1).sql`도 임시 MySQL 8.4에서 검증했습니다.
승인 팀원 2명과 모집글별 재계산 인원(2, 1, 1, 1, 2)이 API에 반영되며 기존 테스트 23개도 통과합니다.
실제 개발 DB는 접속 정보 설정 후 별도로 확인해야 합니다.
테스트 도구에는 httpx 관련 향후 전환 안내 경고 1개가 있으며 테스트 결과에는 영향을 주지 않습니다.

## 다음 구현 순서

1. 프론트 서버 모드에 회원가입/모집글 관리/토큰 갱신/로그아웃 연결
2. 지원과 승인/거절, 승인 팀원/인원수/모집 상태의 트랜잭션 처리
3. 5분 출석 세션, 6자리 문자열 코드, 회원 출석 입력, 중복 방지
4. ESP32 인증/코드 조회/표시 완료 확인과 LCD 연동

출석 코드는 일반 팀원 조회 응답에 포함하지 않고 인증된 기기 API에서만 전달하는 계획입니다.
최신 SQL에서 승인 팀원 등록과 현재 인원 재계산은 반영되었습니다.
남은 사항: 5번 모집글은 2/2명인데 `RECRUITING`입니다. 정원 자동 마감 정책에 맞춰 DB 담당자와 정리해야 합니다.
3번 글은 1/3명으로 재계산되어도 `CLOSED`가 유지되며, 이는 수동 마감으로 허용할 수 있습니다.
동일 모집글의 중복 지원/팀원 등록 UNIQUE 제약과 기술 스택 프로필 구조는 아직 추가되지 않았습니다.
변경 비교는 `docs/db-update-2026-10-07.md`를 참고하세요.
Google AI Plus 구독을 Cloud Run이나 Cloud SQL의 무료 호스팅으로 간주하지 마세요.
배포 시 실제 서버 및 MySQL 과금/크레딧을 각각 확인해야 합니다.
