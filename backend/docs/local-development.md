# 선택 사항: PC에서 백엔드 개발·실행·자동 테스트

배포된 Render API에 접속하거나 Swagger로 테스트할 때는 이 설치 과정이 필요하지 않습니다.
본인 PC에서 Python 코드를 실행하고 수정 사항을 검증할 때 사용하는 안내입니다.
Render의 배포 주소와 설정은 [README](../README.md)를 확인하세요.

## 1. 처음 개발 환경을 준비할 때

명령은 backend 폴더에서 Windows PowerShell로 실행합니다.
가상환경과 .env를 이미 준비했다면 이 초기 준비 단계는 반복하지 않아도 됩니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m scripts.init_env
```

가상환경을 활성화하지 않아도 해당 Python 경로를 직접 지정해 실행할 수 있습니다.
코드 업데이트로 requirements.lock.txt가 바뀌면 라이브러리 설치 명령을 다시 실행합니다.
init_env는 기존 .env를 덮어쓰지 않고, 처음 생성할 때 로컬 JWT 키를 무작위로 만듭니다.
이 로컬 키 생성은 Render의 JWT_SECRET_KEY를 바꾸지 않습니다.

## 2. 로컬 백엔드에서 TiDB에 연결할 때

로컬 .env에는 본인에게 허용된 TiDB 연결 정보를 입력합니다. 아래 한국어 값은 실제 값으로 바꿉니다.

```dotenv
DB_HOST=TiDB_Connect에_표시된_호스트
DB_PORT=4000
DB_NAME=recruitment_db
DB_USER=접두어를_포함한_TiDB_사용자명
DB_PASSWORD="TiDB DB 비밀번호"
DB_SSL=true
JWT_SECRET_KEY="32자_이상의_로컬_개발용_비밀키"
```

포트는 TiDB Connect에 표시된 값을 사용합니다.
DB_HOST에는 https://를 붙이지 않습니다. Render 주소도 DB_HOST로 사용하지 않습니다.
TiDB의 접속 IP 허용 규칙에 본인 PC가 포함되어 있어야 합니다.
Google 계정 로그인 비밀번호와 TiDB DB 비밀번호는 별개입니다.
.env는 GitHub에 올리지 않고 .env.example만 공유합니다. 프로세스 환경변수는 .env보다 우선합니다.
로컬 .env와 Render Environment는 각각 별도로 관리합니다.

이 설정으로 실행한 로컬 API도 같은 공유 TiDB를 사용합니다.
회원가입·모집글 작성·삭제 등은 공유 DB에 반영되므로 테스트 계정과 테스트 모집글로 확인합니다.
현재 공유 DB에 적용된 001·002 변경을 다시 적용하거나 원본 초기화 SQL을 재실행하지 않습니다.

## 3. PC에서 서버 실행

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

| 용도 | 로컬 주소 |
| --- | --- |
| 서버 | http://127.0.0.1:8000 |
| Swagger | http://127.0.0.1:8000/docs |
| 서버 상태 | http://127.0.0.1:8000/health |
| 설정한 DB 연결 상태 | http://127.0.0.1:8000/health/db |

127.0.0.1은 현재 PC를 가리킵니다. 이 명령으로 실행한 로컬 서버에 접속할 때 사용합니다.
배포 서버에 접속할 때는 https://swe-project-u3f0.onrender.com 을 사용합니다.
프론트에서도 테스트할 백엔드에 따라 API 기본 주소를 한 곳에서 바꿉니다.

## 4. 독립 자동 테스트

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock.txt
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

일반 테스트는 별도의 메모리 SQLite와 테스트용 인증 설정을 사용하고 공유 TiDB에는 연결하지 않습니다.
로컬 MySQL 전용 테스트는 환경변수가 없으면 skip됩니다.
실행 방법과 DB 검증 범위는 [지원·승인·내 활동 안내](applications-and-activities.md#5-자동-검증과-재실행)를 확인하세요.

## 5. 새 개발 DB에 원본 샘플을 처음 넣은 경우에만

이 항목은 현재 공유 TiDB의 반복 배포 과정이 아닙니다.
새 빈 개발 DB 초기화는 [Render + TiDB 안내](render-tidb.md)에 따라 진행합니다.
DB 이름과 Users/Posts 등 테이블명의 대소문자는 원본 정의와 맞춥니다.
원본 샘플을 새로 가져와 Users.password에 8자리 숫자가 평문으로 들어 있는 경우에는 다음 변환이 필요합니다.

```powershell
# 대상 수를 읽기만 함
.\.venv\Scripts\python.exe -m scripts.hash_seed_passwords

# 확인한 DB의 평문 샘플 비밀번호를 실제로 해시 변환
.\.venv\Scripts\python.exe -m scripts.hash_seed_passwords --apply
```

이 스크립트는 .env가 가리키는 DB를 사용합니다. --apply는 해당 DB 값을 실제로 변경합니다.
기존 해시는 유지하고 원본 샘플 형식인 8자리 숫자만 Argon2 해시로 변환합니다.
이미 로그인되는 기존 DB나 API로 새로 가입한 사용자에는 이 작업이 필요하지 않습니다.
신규 회원가입 API는 처음부터 해시를 저장합니다.
