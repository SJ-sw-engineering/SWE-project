# Render + TiDB: 처음 연결하기

배포 대상: GitHub `SJ-sw-engineering/SWE-project` 저장소의 `backend` 브랜치, `backend/` 폴더.
main 브랜치로 merge할 필요는 없습니다. 이 수정본을 backend 브랜치에 push한 다음 배포합니다.
서버는 Render Free, DB는 TiDB Cloud Starter의 MySQL Compatible 모드를 사용합니다.
실제 계정/DB 생성과 비밀값 입력은 아래 안내에 따라 사용자가 진행합니다.

## 환경변수는 무엇인가요?

코드에 직접 적지 않고 서버 설정 화면에 넣는 이름과 값의 쌍입니다.
예를 들어 `DB_HOST`에 TiDB 주소를 넣으면 FastAPI가 그 주소로 DB에 접속합니다.
로컬 PC에서는 backend/.env에 넣고, Render에서는 서비스의 Environment 화면에 넣습니다.
GitHub에 .env를 올리는 방식이 아닙니다. Render는 로컬 PC의 .env를 자동으로 알 수 없습니다.

세 가지 비밀번호/키는 역할이 다릅니다.

| 이름 | 역할 | 어디에서 준비하나요? |
| --- | --- | --- |
| 학생 로그인 비밀번호 | 우리 웹서비스에 학번으로 로그인 | Users 데이터 |
| DB_PASSWORD | FastAPI가 TiDB에 접속 | TiDB Connect의 Generate Password/DB 사용자 비밀번호 |
| JWT_SECRET_KEY | FastAPI가 발급한 로그인 토큰의 서명 생성/검증 | 본인 PC에서 무작위 생성 |

Google 로그인은 Render/TiDB 관리 화면에 들어가는 계정 로그인입니다. 위 값들과 별개입니다.

## 1. TiDB의 무료 DB 서버 만들기

1. TiDB Cloud에 로그인하고 My TiDB 페이지를 엽니다.
2. 이미 자동 생성된 Starter 인스턴스가 있으면 MySQL Compatible인지 확인하고 사용할 수 있습니다.
3. 새로 만들려면 Create Resource를 선택합니다.
4. Starter, MySQL Compatible을 선택합니다. 예전 문서의 Serverless는 Starter로 이름이 바뀌었습니다.
5. 이름(예: swe-project-db), AWS, 가까운 지역을 선택합니다.
6. Spending Limit은 0으로 유지하고 무료 인스턴스인지 확인한 뒤 Create를 누릅니다.
7. 인스턴스 상세에서 Connect를 누르고 Public 연결 정보를 확인합니다.
8. Generate Password를 눌러 DB 비밀번호를 준비하고 안전하게 보관합니다.
9. Host, Port, Username을 기록합니다. Username의 prefix까지 전체를 사용합니다.

각 서비스는 서로 다른 회사이므로 TiDB와 Render의 지역 이름이 정확히 같을 필요는 없습니다.
가능하면 가까운 지역을 고릅니다. 비용이 드는 TiDB Essential/Dedicated로 변경하지 않습니다.
무료 MySQL Compatible Starter에는 인스턴스별 5 GiB 행 데이터와 월 5천만 RU 등의 한도가 있습니다.
무료 인스턴스는 한도 도달 시 사용이 제한될 수 있으므로 무제한 무료로 이해하지 마세요.

## 2. 테이블과 샘플 데이터 넣기

TiDB는 MySQL 호환이므로 기존 MySQL용 SQL을 기반으로 사용합니다. PostgreSQL로 변환할 필요가 없습니다.
SQL 파일은 실행 시 테이블/데이터를 만드는 명령문이며, FastAPI는 생성된 실제 DB를 조회합니다.

SQL Editor에서 다음을 실행해 DB를 만들 수 있습니다.

```sql
CREATE DATABASE IF NOT EXISTS recruitment_db;
USE recruitment_db;
```

기존 `recruitment_db (1).sql`의 CREATE TABLE/INSERT/UPDATE 문을 순서대로 실행합니다.
SQL Editor에서 여러 문장을 실행할 때는 실행할 부분 전체를 선택하고 Run을 누릅니다.
원본에 DROP TABLE이 있으므로 **처음 만드는 빈 개발 DB에서만** 원본 전체를 실행하세요.
이미 데이터가 있으면 재초기화하지 말고 DB 담당자와 필요한 변경만 적용합니다.
AI로 SQL을 새로 생성할 필요는 없습니다. 기존 SQL을 직접 실행합니다.

확인 SQL:

```sql
SHOW TABLES FROM recruitment_db;
SELECT COUNT(*) FROM recruitment_db.Users;
SELECT COUNT(*) FROM recruitment_db.Posts;
```

첨부 수정본 기준으로 테이블 7개, 사용자 70명, 모집글 5개입니다.
실제 TiDB에서 SQL을 적용하는 중 호환 오류가 발생하면 그 오류 문구를 확인해야 합니다.

## 3. JWT 키 만들기

CMD 또는 PowerShell에서 실행합니다. `secrests`가 아니라 **secrets**입니다.

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

화면에 나온 문자열을 JWT_SECRET_KEY의 값으로 사용합니다. 다른 사이트에 전송하는 명령이 아닙니다.
명령을 실행할 때마다 다른 값이 나오므로 생성한 값 하나를 서버 설정에 저장해서 계속 사용합니다.
기존 backend/.env에 본인이 사용 중인 키가 있으면 새로 만들지 않고 그 값을 사용할 수도 있습니다.
키를 바꾸면 기존 로그인 토큰이 무효화됩니다. 이 키는 토큰 내용을 암호화하는 키가 아니라 서명용 비밀키입니다.

## 4. 로컬 PC에서 TiDB 연결 및 비밀번호 해시 변환

backend/.env의 DB 설정을 아래처럼 본인 값으로 바꿉니다. 예시 주소/사용자명은 실제 값이 아닙니다.

```dotenv
DB_HOST=본인의_TiDB_Host
DB_PORT=4000
DB_NAME=recruitment_db
DB_USER=본인의_접두어.root
DB_PASSWORD="TiDB에서 생성한 DB 비밀번호"
DB_SSL=true
```

포트는 Connect 화면의 값을 사용합니다. 호스트에는 https:// 또는 mysql://를 붙이지 않습니다.
JWT_SECRET_KEY에도 3단계에서 생성한 키가 있어야 합니다.
DB_SSL=true는 TLS 연결과 서버 인증서/호스트 이름 검증을 활성화합니다.
로컬 .env는 GitHub에 올리지 않습니다.

backend 폴더에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m scripts.hash_seed_passwords
.\.venv\Scripts\python.exe -m scripts.hash_seed_passwords --apply
```

이 명령은 로컬 PC에서 **TiDB에 접속하여** 샘플 Users.password를 Argon2 해시로 바꿉니다.
기존 테스트 로그인 비밀번호는 그대로 사용합니다. 이미 해시인 값은 변환하지 않습니다.
Render 무료 서비스의 Shell에 들어갈 필요는 없습니다.

연결할 수 없다면 TiDB의 Settings > Networking 또는 Connect에 표시된 IP 허용 설정에서
본인 PC의 현재 공인 IP를 허용했는지 확인하세요. 연결 오류를 해결하려고 TLS 검증을 끄지 마세요.

## 5. GitHub에 수정 코드 push

TLS 연결 지원이 추가된 app/config.py, app/database.py와 관련 안내/테스트 파일을 backend 브랜치에 push합니다.
사용자가 push하며, .env와 비밀값은 포함하지 않습니다. API 경로와 JSON 응답 형식은 그대로입니다.

## 6. Render 웹 서비스 생성

1. Render 대시보드에서 New > Web Service를 선택합니다.
2. GitHub 연결에서 SJ-sw-engineering/SWE-project를 선택합니다.
3. 아래 값을 입력합니다.

| 항목 | 값 |
| --- | --- |
| Name | 원하는 이름, 예: swe-project-backend |
| Branch | backend |
| Runtime | Python 3 |
| Root Directory | backend |
| Build Command | pip install -r requirements.lock.txt |
| Start Command | python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT |
| Instance Type | Free |
| Health Check Path | /health |

추가 서버나 Render Postgres는 만들 필요가 없습니다. $PORT는 Render가 제공하므로 그대로 둡니다.
이미 웹 서비스를 만들었다면 새 서비스를 중복 생성하지 않고 Settings/Environment를 수정합니다.

## 7. Render 환경변수 입력

서비스 생성 화면의 Environment Variables 또는 기존 서비스의 왼쪽 Environment 메뉴에서
Add Environment Variable을 누릅니다. Key 칸과 Value 칸에 한 줄씩 입력합니다.
표의 한국어 설명을 그대로 넣지 말고 본인의 실제 값을 입력하세요. 값 주위에 따옴표는 넣지 않습니다.

| Key | Value |
| --- | --- |
| PYTHON_VERSION | 3.12.14 |
| DB_HOST | TiDB Connect에 표시된 Host |
| DB_PORT | TiDB Connect의 Port, 일반적으로 4000 |
| DB_NAME | recruitment_db |
| DB_USER | TiDB Connect의 Username 전체 |
| DB_PASSWORD | TiDB에서 준비한 DB 비밀번호 |
| DB_SSL | true |
| JWT_SECRET_KEY | 3단계에서 생성한 문자열 |

이 설정을 저장한 뒤 Deploy Web Service 또는 Save, rebuild, and deploy를 누릅니다.
DB_PASSWORD는 예전 안내의 not-connected-yet 임시값을 실제 TiDB 비밀번호로 교체합니다.
현재 코드는 DATABASE_URL을 읽지 않으므로 위 DB_* 항목을 각각 사용합니다.
ACCESS_TOKEN_EXPIRE_MINUTES는 생략하면 30입니다.
나중에 프론트엔드를 배포하면 CORS_ORIGINS에 해당 주소를 JSON 배열로 설정합니다.

## 8. Render에서 TiDB로 들어오는 접속 허용

Render 서비스 상세의 Connect > Outbound에서 해당 서비스가 사용하는 IP 범위 목록을 확인합니다.
TiDB 공개 엔드포인트의 IP 허용 규칙에 그 범위를 등록합니다.
Render의 IP 범위는 같은 지역의 여러 서비스가 공유하므로 DB 비밀번호/TLS도 함께 유지합니다.
로컬에서만 연결되고 Render에서 시간 초과가 나면 이 설정을 우선 확인하세요.
접속 허용 설정은 사용자가 계정 화면에서 진행합니다.

## 9. 연결 확인

Render가 제공한 실제 서비스 주소 뒤에 경로를 붙여 확인합니다.

| 경로 | 기대 결과 |
| --- | --- |
| /health | 서버 실행 확인: status=ok |
| /health/db | TiDB 연결 확인: database=connected |
| /api/posts | 샘플 모집글 목록과 total=5 |
| /docs | API 문서 |

/health/db의 성공은 연결 확인이며 테이블/샘플 데이터 확인은 /api/posts로 합니다.
/docs에서 POST /api/auth/login에 학번 20191001, 비밀번호 20000115를 JSON으로 입력하면
해시 변환 후 로그인 토큰을 받을 수 있습니다. 이는 첨부 샘플 계정으로만 사용하는 값입니다.

## 참고 문서

- TiDB 생성: https://docs.pingcap.com/tidbcloud/create-tidb-cluster-serverless/
- TiDB 연결: https://docs.pingcap.com/tidbcloud/connect-via-standard-connection-serverless/
- PyMySQL: https://docs.pingcap.com/developer/dev-guide-sample-application-python-pymysql/
- Render 환경변수: https://render.com/docs/configure-environment-variables
- Render Outbound IP: https://render.com/docs/outbound-ip-addresses

코드/설정 검증과 별개로 실제 TiDB 계정 연결은 본인 접속 정보를 설정한 후 확인해야 합니다.
