# 지원·승인·내 활동 API와 DB 검증

2026-10-28 / API 버전 0.3.0

frontend 브랜치 `5bf7f33`의 apply/applicants/decide/myApplications/myTeams 함수에 맞춘 서버 계약입니다.
이번 작업은 백엔드 코드와 DB 변경 SQL 작성입니다. 프론트 코드 변경, GitHub push/merge, Render 배포, 실제 TiDB 변경은 수행하지 않았습니다.

## 1. 추가 API 5개

모두 `Authorization: Bearer <access_token>`이 필요하고, 성공 응답은 JSON입니다.
개인별 응답에는 Cache-Control: no-store를 설정합니다.

| 메서드·경로 | 프론트 함수 | 권한 | 성공 |
| --- | --- | --- | --- |
| POST /api/posts/{post_id}/applications | apply | 로그인한 지원자 | 201 ApplicationResponse |
| GET /api/posts/{post_id}/applications | applicants | 해당 팀장 | 200 배열 |
| PATCH /api/applications/{application_id} | decide | 해당 팀장 | 200 ApplicationResponse |
| GET /api/users/me/applications | myApplications | 본인 | 200 배열 |
| GET /api/users/me/teams | myTeams | 본인 | 200 배열 |

### 지원하기

```json
{"message":"프로젝트에 함께 참여하고 싶습니다."}
```

message는 앞뒤 공백 제거 후 1~5000자입니다. applicant_id/post_id/status를 본문에 추가하지 않습니다.
지원자는 토큰에서 결정하며, 글 ID는 경로에서 받습니다.

응답 예시(실제 ID/시간은 응답을 사용):

```json
{
  "id": 10,
  "post_id": 6,
  "applicant_id": "test_member_a",
  "message": "프로젝트에 함께 참여하고 싶습니다.",
  "status": "PENDING",
  "applied_at": "2026-10-28T00:00:00Z"
}
```

- 본인 모집글 지원: 409.
- 같은 글 중복 지원: 409. 거절된 지원서가 있어도 재지원하지 않습니다.
- 마감 또는 정원 초과: 409.
- 지원만으로 현재 팀 인원은 늘어나지 않습니다.

### 지원자 목록

지원 응답과 같은 필드에 `name`을 추가한 배열입니다. ID 오름차순입니다.
비어 있으면 `[]`이며, 팀장 이외의 사용자는 403입니다.
신청 내용과 신청자 ID는 해당 팀장/신청자 본인에게만 제공합니다.

### 승인 또는 거절

```json
{"status":"APPROVED"}
```

또는:

```json
{"status":"REJECTED"}
```

- PENDING만 처리할 수 있습니다. 처리된 지원서 재처리는 409입니다.
- 팀장 이외는 403입니다.
- 승인 시 Applications 상태, ApprovedMembers 행, Posts.current_size/status를 한 트랜잭션으로 처리합니다.
- 현재 인원은 팀장 1명 + 승인 팀원 수입니다. 정원 도달 시 CLOSED입니다.
- 같은 팀의 쓰기는 Posts 행을 먼저 잠가 동시 승인·정원 수정·마감·삭제와 직렬화합니다.
- 정원이 찼을 때 다른 지원서를 승인하면 409이며 해당 지원서는 PENDING으로 유지됩니다.
- 정원이 찬 뒤에도 남은 지원서를 거절할 수 있습니다.
- 프론트 로컬 구현과 같이, 수동 마감 전에 접수된 PENDING은 정원이 남아 있으면 승인할 수 있습니다. 마감 상태는 유지되고 새 지원은 받지 않습니다.

### 내 지원 현황

본인 지원 응답에 `post` 요약 객체를 추가한 배열입니다. 최신 지원 ID부터 정렬합니다.
post 필드는 id/author_name/title/category/target_size/current_size/status/created_at으로 기존 공개 요약과 같습니다.

```json
[
  {
    "id":10,"post_id":6,"applicant_id":"test_member_a","message":"지원 내용",
    "status":"APPROVED","applied_at":"2026-10-28T00:00:00Z",
    "post":{
      "id":6,"author_name":"테스트팀장","title":"팀 모집","category":"Web/Frontend",
      "target_size":2,"current_size":2,"status":"CLOSED","created_at":"2026-10-28T00:00:00Z"
    }
  }
]
```

### 내 팀

내가 작성한 모집글과 내가 ApprovedMembers에 등록된 모집글의 요약 배열입니다.
작성자는 role=LEADER, 승인된 팀원은 role=MEMBER입니다. PENDING/REJECTED만 있는 팀은 포함하지 않습니다.
모집이 마감된 팀도 포함합니다. 정렬은 모집글 created_at, id 내림차순입니다.

## 2. DB 변경: 테이블 수는 8개 유지

| 테이블 | 추가할 제약 | 목적 |
| --- | --- | --- |
| Applications | UNIQUE(post_id, applicant_id) | 중복 지원 방지 |
| ApprovedMembers | UNIQUE(post_id, member_id) | 같은 팀에 중복 등록 방지 |
| ApprovedMembers | UNIQUE(application_id) | 한 지원서로 중복 승인 방지 |

또한 현재 인원을 승인 팀원 기준으로 다시 계산하고, 정원이 찬 글을 마감합니다. 이미 수동 마감한 글은 계속 마감 상태로 유지합니다.
원본 전체 초기화 SQL이나 비밀번호 해시 변환을 다시 실행할 필요는 없습니다.

### 적용 순서

1. 팀원들에게 잠시 DB/API 쓰기 테스트를 멈춰 달라고 알립니다.
2. TiDB SQL Editor에서 `migrations/002_applications_precheck.sql` 전체를 실행합니다. 파일 안에 USE recruitment_db가 포함되어 있습니다.
3. 여섯 SELECT 결과가 모두 빈 결과인지 확인합니다. 행이 있으면 DB 담당자가 정합성을 먼저 정리해야 합니다. 자동으로 중복 행을 삭제하지 않습니다.
4. `migrations/002_applications_unique.sql` 전체를 실행합니다. 세 고유 제약과 인원/마감 보정을 적용합니다.
5. `migrations/002_applications_verify.sql` 전체를 실행해 아래 결과를 확인합니다.
6. 백엔드 코드를 backend 브랜치에 push하고 Render에 0.3.0이 배포되었는지 확인합니다.

DDL은 전체 롤백되지 않으므로 변경 SQL은 한 번 적용합니다. 도중 실패하면 SHOW INDEX로 이미 생성된 제약을 확인하고 누락된 ALTER만 실행합니다.
같은 SQL을 재실행하다 인덱스 이름 중복 오류가 나더라도 테이블을 지우지 않습니다.

### 적용 확인 결과

- 첫 번째 결과: 고유 인덱스 3개에 대한 총 5행. 복합 인덱스는 컬럼마다 한 행이고 NON_UNIQUE=0입니다.
- 두 번째 결과: 현재 인원과 실제 승인 인원 불일치 없음 → 0행.
- 세 번째 결과: 정원이 찼는데 마감되지 않은 글 없음 → 0행.
- 네 번째 결과: 승인된 지원서와 승인 멤버의 연결 오류 없음 → 0행.
- 테이블 수: 8개 그대로.

2026-10-28 실제 TiDB 읽기 전용 점검에서 여섯 사전 점검 결과는 모두 0행이었으며, 위 고유 제약은 아직 없었습니다.
이는 점검 시점 결과입니다. 실제 적용 직전에는 사전 점검을 다시 실행하세요.
원본 샘플의 5번 글이 승인 팀원 기준 2/2인데 RECRUITING이라면 보정 SQL 적용 후 CLOSED가 됩니다.

## 3. Swagger + 실제 TiDB 테스트 순서

배포 후 /docs에 버전 0.3.0과 위 5개 API가 보여야 합니다.
기존 테스트 계정을 바꾸기보다, 아래처럼 새 계정 세 개와 테스트 모집글 하나를 사용합니다.

| 역할 | 예시 username | 예시 name |
| --- | --- | --- |
| 팀장 | test_leader_1028 | 테스트팀장 |
| 지원자 A | test_member_a_1028 | 테스트팀원A |
| 지원자 B | test_member_b_1028 | 테스트팀원B |

비밀번호 예시는 `TestPass!1028`입니다. 같은 계정이 이미 있으면 로그인하거나 뒤 숫자를 바꿉니다.
회원가입 요청에는 username/name/password만 사용합니다.
각 계정으로 로그인하여 받은 접근 토큰을 역할별로 구분합니다. Swagger Authorize에는 실행할 역할의 접근 토큰 문자열만 입력합니다.

### A. 팀장: 모집글 작성

POST /api/posts:

```json
{"title":"지원 승인 API 검증","content":"검증 후 삭제할 테스트 글","category":"Web/Frontend","target_size":2}
```

201 응답의 id를 P로 기록합니다. 이후의 {post_id}는 실제 P로 바꿉니다.
초기 상태는 current_size=1, status=RECRUITING입니다.
팀장으로 자기 글에 지원하면 409여야 합니다.

### B. 지원자 A와 B: 각각 지원

각 역할의 접근 토큰으로 Authorize를 바꾼 뒤 POST /api/posts/P/applications를 호출합니다.

```json
{"message":"지원자 A의 테스트 지원입니다."}
```

B도 본인 내용으로 지원합니다. 각각 201, status=PENDING이어야 합니다. 반환된 id를 A_ID, B_ID로 기록합니다.
A가 같은 글에 다시 지원하면 409여야 합니다.
각자의 GET /api/users/me/applications에 본인 지원과 post가 보이고, GET /api/users/me/teams에는 아직 P가 없어야 합니다.

DB 확인은 아래 묶음 전체를 선택해 실행합니다. 123은 실제 P로 바꾸세요.

```sql
USE recruitment_db;
SET @test_post_id = 123;
SELECT id, post_id, applicant_id, message, status, applied_at
FROM Applications WHERE post_id = @test_post_id ORDER BY id;
SELECT post_id, member_id, application_id
FROM ApprovedMembers WHERE post_id = @test_post_id;
SELECT id, target_size, current_size, status FROM Posts WHERE id = @test_post_id;
```

기대 결과: Applications 두 행 PENDING, ApprovedMembers 0행, Posts는 1/2 RECRUITING입니다.
이 SELECT 묶음은 다음 단계마다 다시 실행해 비교할 수 있습니다.

### C. 지원자 권한 확인

A 토큰으로 GET /api/posts/P/applications 또는 PATCH /api/applications/A_ID를 호출하면 403입니다.
지원자가 자기 지원을 승인할 수 없어야 합니다.

### D. 팀장: A 승인

팀장 토큰으로 GET /api/posts/P/applications를 호출하여 이름/지원 내용/상태를 확인합니다.
PATCH /api/applications/A_ID:

```json
{"status":"APPROVED"}
```

200 후 DB 기대 결과:

- A의 지원서: APPROVED.
- B의 지원서: PENDING.
- ApprovedMembers: P/A/A_ID 조합 한 행.
- Posts: current_size=2, status=CLOSED.

A의 GET /api/users/me/teams에는 P와 role=MEMBER, 팀장에게는 role=LEADER가 보여야 합니다.
A의 GET /api/posts/P/context에도 my_application.status=APPROVED가 보여야 합니다.

### E. 팀장: 정원 초과와 재처리 확인

- B_ID를 APPROVED로 처리 → 409. DB에서 B는 PENDING이고 팀원 행은 추가되지 않아야 합니다.
- A_ID를 다시 APPROVED 또는 REJECTED 처리 → 409. 기존 팀원 행은 한 행 그대로여야 합니다.

### F. 팀장: B 거절

PATCH /api/applications/B_ID:

```json
{"status":"REJECTED"}
```

200 후 B는 REJECTED, B의 팀원 행은 없고 Posts는 2/2 CLOSED 그대로여야 합니다.
B의 내 지원에는 REJECTED가 보이고 내 팀에는 P가 없어야 합니다. 재지원하면 409입니다.

### G. DB 전체 정합성 확인

`002_applications_verify.sql`을 다시 실행합니다. 첫 번째 인덱스 조회 외의 세 검사는 모두 0행이어야 합니다.
다른 팀의 실제 데이터가 원래부터 불일치하면 그 행도 표시되므로 DB 담당자와 해당 글을 확인합니다.

선택 확인: 팀장으로 테스트 글 P를 삭제한 뒤 위 SELECT로 해당 글의 지원/팀원 행도 없어졌는지 확인합니다.
삭제된 팀의 지원은 내 지원/내 팀에서도 사라집니다. 실제 사용 중인 팀의 ID로 삭제 테스트하지 않습니다.

## 4. 프론트 담당자 연결 사항

- js/server.js에 apply/applicants/decide/myApplications/myTeams를 추가하고 인증 헤더를 보냅니다.
- 목록 세 API는 페이지 객체가 아닌 배열을 반환하므로 기존 로컬 화면의 map 처리를 재사용할 수 있습니다.
- 지원자 목록의 name, 내 지원의 post, 내 팀의 role은 로컬 어댑터의 필드 이름과 같습니다.
- app.js 서버 모드에서 내 지원/내 팀/지원/지원자 관리 페이지와 메뉴를 허용합니다.
- 상세 화면은 기존 공개 상세 + /context를 조합합니다. is_owner로 팀장 버튼을 표시하고 my_application.status로 지원 상태를 표시합니다.
- 403은 권한 없음, 409는 중복/마감/정원/재처리 안내입니다. 응답 detail을 적절히 표시합니다.
- approve/reject 뒤 지원자 목록과 모집글을 다시 조회하여 인원/마감 상태를 갱신합니다.
- 서버 모드 기능을 사용할 때 localStorage 기록은 실제 TiDB 데이터와 합쳐지지 않습니다.

## 5. 자동 검증과 재실행

```powershell
# backend 폴더에서 실행
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

일반 테스트는 SQLite를 사용합니다. 로컬 MySQL 테스트 4개는 전용 환경변수가 없으면 skip됩니다.
2026-10-28 결과: SQLite 독립 테스트 81개 통과, 별도 로컬 MySQL 8.4 테스트 4개 통과.

MySQL 테스트는 기존 구조에서 UNIQUE가 없는 상태를 구성한 뒤 실제 001/002 SQL을 적용합니다.
이후 중복 제약 3개, 카운트/마감 보정, 동시에 마지막 한 자리 승인 시 200/409, 동시 중복 지원 시 201/409,
승인 중 DB 삽입 실패 시 Applications/ApprovedMembers/Posts 전체 롤백을 확인합니다.

재실행하려면 별도의 로컬 MySQL 컨테이너를 준비하고 다음 변수를 그 컨테이너의 값으로 설정합니다.

```powershell
$env:RECRUITMENT_MYSQL_TEST_PORT = '로컬 테스트 컨테이너의 실제 포트'
$env:RECRUITMENT_MYSQL_TEST_PASSWORD = '그 컨테이너의 root 비밀번호'
.\.venv\Scripts\python.exe -m pytest tests/test_mysql_applications.py -q -p no:cacheprovider
```

이 테스트는 127.0.0.1로만 연결하고 recruitment_api_test_로 시작하는 무작위 DB를 생성/제거합니다.
프로젝트의 .env 또는 TiDB 주소를 테스트 대상으로 사용하지 않습니다.
실제 TiDB에서의 최종 확인은 위 Swagger 시나리오와 읽기 SQL로 진행합니다.

## 6. 다음 단계와 진척도

다음 구현은 출석 시작/종료/코드 인증/회차 이력/팀원 현황 API와 장치 코드 조회/ACK API입니다.
일반 사용자 조회에는 출석 코드를 넣지 않고, 인증된 ESP32에만 코드를 제공합니다.

전체 100을 proposal 기능이 프론트·서버·DB·실기기까지 연결되어 검증된 상태로 정의하면 현재는 약 60~65%로 추정합니다.
이는 작업 범위에 따른 추정이며 테스트 개수나 API 개수로 계산한 수치는 아닙니다.
현재 일반 웹 백엔드의 주요 기능이 구현되었고, 프론트의 추가 API 연결과 출석/ESP32 통합 검증이 남아 있습니다.

ESP32는 지금부터 LCD 기본 출력과 Wi-Fi 연결을 점검할 수 있습니다.
서버 연동은 다음 출석·장치 API의 요청/응답을 확정한 뒤 함께 시작하는 것이 좋습니다.
LCD 모델/연결 방식/핀 배선/개발 환경을 확인하면 실제 펌웨어 작성으로 이어갈 수 있습니다.
최소 연결은 ESP32가 HTTPS로 주기 조회 → LCD 출력 → ACK 전송하는 구조로 진행합니다.
