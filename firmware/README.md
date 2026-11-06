# ESP32 → Wi-Fi → Render 출석 코드 표시

Arduino IDE용 스케치: `attendance_display/attendance_display.ino`.
ESP32-WROOM-32 계열 개발 보드와 HD44780 호환 16×2 I2C LCD용입니다.
확인된 배선은 **SDA=GPIO21, SCL=GPIO22**입니다.
LCD 초기화·코드 출력·표시 완료 ACK·만료 시 대기 화면 전환을 구현했습니다.
처음에는 `LCD_ENABLED=0`으로 Serial 통신만 확인한 뒤, `1`로 바꾸어 LCD와 ACK를 시험합니다.

## 1. 연결 구조

```text
팀장 웹 → Render에서 출석 시작
ESP32 → Wi-Fi → Render에서 코드 조회 → LCD 출력 → Render에 ACK
팀원 웹 → Render에 코드 입력 → TiDB에 출석 기록
```

LCD의 기존 배선은 유지합니다. USB는 스케치 업로드/전원/Serial 확인용으로 사용할 수 있습니다.
ESP32는 Render의 공개 HTTPS 주소에 접속하는 클라이언트입니다. PC와 같은 Wi-Fi에 있을 필요는 없고 인터넷 연결이 필요합니다.

## 2. 서버에서 장치 준비

백엔드 0.4.0 배포 후 Swagger에서 팀장으로 로그인합니다.
2026-11-02 사용자 수동 배포 이후 공개 /openapi.json에서 0.4.0과 출석/장치 API 반영을 확인했습니다.
기존 0.2.0 배포 문제는 해소되었으며, 이 테스트 때문에 다시 배포할 필요는 없습니다.
새 계정 생성부터 진행하려면 [전체 수동 테스트](../backend/docs/full-system-test.md)를 참고하세요.
POST /api/posts/{팀ID}/devices를 실행하고 응답의 id와 device_credential을 기록합니다.
DB에 저장된 해시가 아니라 이 응답에서 받은 원문 키를 사용합니다.
**id와 device_credential은 반드시 같은 등록 응답에서 받은 한 쌍을 사용합니다.**
등록 POST를 다시 실행하면 다른 ID/키가 발급됩니다. 출석을 시작할 때마다 등록하지 않습니다.

## 3. Arduino IDE 준비

ESP32-WROOM은 Espressif 모듈 이름입니다. **Arduino IDE 및 Arduino용 ESP32 소프트웨어 패키지는 WROOM 보드에서도 사용합니다.**
코드의 Arduino.h/WiFi.h는 이 개발 환경의 라이브러리이므로 지우지 않습니다.

1. 데이터 통신이 가능한 USB 케이블로 보드를 PC에 연결합니다.
2. Arduino IDE의 Boards Manager(보드 매니저)에서 **esp32 by Espressif Systems 3.x**를 설치합니다.
   보드 목록이 없다면 환경설정의 추가 보드 매니저 URL에 공식 주소 `https://espressif.github.io/arduino-esp32/package_esp32_index.json`을 추가합니다.
3. Library Manager(라이브러리 매니저)에서 **ArduinoJson by Benoit Blanchon 7.x**를 설치합니다.
4. 같은 곳에서 **hd44780 by Bill Perry**를 설치합니다. 검증한 버전은 1.3.2입니다.
   이 코드는 LiquidCrystal_I2C 라이브러리를 사용하지 않습니다. 기존 설치 라이브러리를 삭제할 필요는 없습니다.
5. File → Open에서 **firmware/attendance_display/attendance_display.ino**를 엽니다.
6. Tools → Board → esp32에서 일반 ESP32-WROOM-32/32D/32E 개발 보드이면 **ESP32 Dev Module**을 선택합니다.
   이미 LCD 테스트에 성공한 정확한 보드 항목이 있다면 그 설정을 사용합니다.
   이름에 WROOM이 있다는 이유로 ESP32-WROOM-DA Module이나 Arduino Nano ESP32를 선택하지 않습니다.
   모듈이 ESP32-S3-WROOM/C3 등이라면 보드 항목은 해당 칩에 맞춰야 합니다.
7. Tools → Port에서 연결된 **COM 포트**를 선택합니다. 모르면 USB를 뺐을 때 사라지고 꽂으면 생기는 포트를 확인합니다.
8. Upload Speed는 우선 **115200**으로 설정하고, Flash/Partition 등은 해당 보드 기본값을 유지합니다.
9. 아래 config.h를 만든 뒤 Verify(체크 표시) → Upload(오른쪽 화살표)를 누릅니다.
10. 업로드 후 Tools → Serial Monitor를 열고 **115200 baud**로 맞춥니다. 초기 로그를 놓쳤으면 보드의 EN/RESET을 누릅니다.

Connecting...에서 멈추면 BOOT 버튼을 누른 채 업로드를 시작하고 쓰기가 시작될 때 놓습니다.
포트가 없으면 데이터 케이블과 보드의 USB-Serial 칩에 맞는 드라이버부터 확인합니다.

검증 환경은 ESP32 core 3.3.12, ArduinoJson 7.4.3, hd44780 1.3.2, ESP32 Dev Module입니다.
2026-11-02에 임시 가짜 Wi-Fi/장치 설정으로 두 모드의 전체 빌드에 통과했습니다.
Serial 전용 모드는 프로그램 영역 78%, LCD 활성 모드는 81%를 사용했습니다.
실제 사용자 보드 업로드와 LCD 화면 확인은 아래 절차로 진행합니다.

### 업로드할 파일과 헤더

```text
firmware/attendance_display/
  attendance_display.ino  ← IDE에서 열고 Upload하는 스케치
  config.h                ← 직접 복사·작성하는 로컬 설정; Git 제외
  config.example.h        ← 설정 양식
  lcd_adapter.h           ← LCD 초기화/출력
  root_ca.h               ← HTTPS 인증용 공개 인증서
```

**.ino를 열어 업로드하면 include된 헤더와 라이브러리를 함께 컴파일한 하나의 펌웨어가 전송됩니다.**
.h 파일을 보드에 각각 업로드하지 않습니다. 헤더가 같은 폴더에 있는 것은 정상이며 이름과 include가 맞아야 합니다.
config.h가 없으면 빈 config.example.h로 컴파일되지만 실제 접속은 시작하지 않고 설정 안내를 출력합니다.
config.h와 config.example.h가 함께 있어도 둘 중 하나만 include하므로 중복 선언하지 않습니다.
이 폴더에 다른 테스트용 .ino를 추가하면 setup/loop가 중복될 수 있으므로 다른 스케치는 별도 폴더에 보관합니다.
IDE가 스케치를 다른 위치로 복사했다면 헤더와 config.h도 그 스케치 폴더에 함께 복사해야 합니다.

## 4. Wi-Fi와 장치 키 입력

config.example.h를 같은 폴더의 config.h로 복사합니다. config.h는 Git에서 제외됩니다.

```cpp
static const char WIFI_SSID[] = "공유기 또는 핫스팟 이름";
static const char WIFI_PASSWORD[] = "Wi-Fi 비밀번호";
static const char API_BASE_URL[] = "https://swe-project-u3f0.onrender.com";
static const unsigned int DEVICE_ID = 1; // 실제 장치 등록 응답 ID
static const char DEVICE_KEY[] = "esp_장치등록응답에서받은키";

#define LCD_ENABLED 0      // 첫 Serial 테스트는 0, LCD 테스트는 1
#define LCD_SDA_PIN 21     // 사용자가 확인한 배선
#define LCD_SCL_PIN 22
#define LCD_I2C_ADDRESS 0  // 지원하는 I2C 백팩 주소/핀 매핑 자동 탐색
```

예시 값은 본인 값으로 바꿉니다. API 주소 끝에 /docs나 /api를 붙이지 않습니다.
먼저 일반 ESP32 Dev Module에서 사용할 수 있는 2.4GHz 개인 공유기 또는 호환되는 휴대폰 핫스팟으로 시험하면 됩니다.
학교의 브라우저 로그인/기업 인증 Wi-Fi는 이 SSID·비밀번호 예제만으로 연결되지 않을 수 있습니다.
DEVICE_KEY는 사용자 로그인 토큰, JWT 비밀키, DB 비밀번호, Google 계정 비밀번호와 별개입니다.
기존 config.h가 있다면 마지막 LCD 설정 4줄을 추가합니다. 설정을 바꾸면 다시 업로드해야 합니다.
Wi-Fi 비밀번호나 장치 키에 큰따옴표/역슬래시가 있다면 C++ 문자열에 맞게 이스케이프합니다.

코드는 WiFi.begin으로 접속하고 연결이 끊기면 재연결을 시도합니다.
인터넷 시간 동기화가 끝난 뒤 HTTPS를 호출합니다. 네트워크에서 NTP가 차단되면 시간 동기화 단계에서 멈출 수 있습니다.

## 5. Serial에서 네트워크부터 확인

프론트엔드가 아직 연결되지 않아도 Swagger로 시작할 수 있습니다.

1. Render의 [Swagger](https://swe-project-u3f0.onrender.com/docs)를 열고 출석/장치 API가 있는지 확인합니다.
   서버가 sleep 중이면 웹에서 먼저 깨우고 API 응답을 확인합니다. 첫 기기 요청이 시간 초과되어도 다음 조회에서 재시도합니다.
2. 팀장 계정으로 POST /api/auth/login을 실행하고 access_token을 Authorize의 HTTPBearer에 넣습니다.
3. 팀장이 만든 모집글의 ID를 P로 기록합니다. 장치를 처음 등록한다면 POST /api/posts/P/devices를 실행합니다.
   응답의 id를 D, device_credential을 K로 기록합니다. 이미 D/K를 보관했다면 재등록하지 않습니다.
4. config.h에 실제 Wi-Fi SSID/비밀번호, DEVICE_ID=D, DEVICE_KEY=K를 입력합니다.
5. **LCD_ENABLED=0**으로 두고 Verify → Upload합니다. Serial Monitor를 115200으로 열고 EN/RESET을 누릅니다.
6. 다음 순서의 메시지를 확인합니다.

```text
Serial-only mode (LCD_ENABLED=0); LCD disabled, ACK withheld.
Wi-Fi connected. Synchronizing time for HTTPS.
Time synchronized. Starting HTTPS polling.
HTTPS display: 200
Server: no active attendance session for DEVICE_ID=1.
```

7. Swagger에서 POST /api/posts/P/attendance-sessions를 실행하고 본문에 `{ "device_id": D }`를 넣습니다.
   D는 예시 문자가 아니라 실제 숫자로 바꿉니다. 응답 id를 S로 기록합니다.
8. 약 10초 안팎의 다음 조회에서 아래처럼 표시되는지 확인합니다. 숫자는 예시이며 서버가 생성한 실제 코드가 출력됩니다.

```text
HTTPS display: 200
Received attendance code: 000047
```

9. HTTP 200만으로 코드 수신을 확정하지 말고 **Received attendance code**까지 확인합니다.
   session=null이면 아직 해당 장치로 시작한 회차가 없거나 만료/종료된 것입니다.
10. GET /api/posts/P/attendance-sessions에서 이 회차의 display_ack=false를 확인합니다.
    Serial 전용 테스트에서는 **HTTPS ACK: 200이 나오지 않는 것이 정상**입니다. Swagger에서 수동 ACK를 보내지 않습니다.
11. 팀장 토큰으로 POST /api/attendance-sessions/S/close를 실행합니다. IDLE 로그를 확인합니다.
    종료하지 않은 회차가 남아 있으면 다음 시작이 409이므로 먼저 종료합니다.

활성 회차는 약 2초, 대기 상태는 약 10초 간격으로 조회합니다.
네트워크 작업을 별도 태스크로 수행하므로 HTTPS 연결이 지연되어도 메인 루프의 표시 만료 처리는 계속됩니다.
사용자 JWT는 보내지 않고 X-Device-Key 헤더만 보냅니다.

## 6. LCD 출력과 자동 ACK 테스트

1. config.h에서 **LCD_ENABLED=1**로 바꾸고 다시 Verify → Upload합니다.
2. Serial에서 `LCD ready: 16x2, SDA=21, SCL=22, address=0x27`과 같은 로그를 확인합니다. 탐지 주소는 LCD마다 다를 수 있습니다.
3. LCD가 다음 대기 화면을 표시해야 합니다. SDA/SCL은 확인된 기존 배선을 유지합니다.

```text
Attendance
Waiting...
```

4. Swagger에서 해당 D로 **새 출석 회차**를 시작합니다.
5. Serial의 6자리와 LCD의 6자리가 같은지 확인합니다. 앞자리 0도 유지됩니다.

```text
Attendance code
Code: 000047
```

6. Serial에서 `LCD code written; queuing display ACK.`와 `HTTPS ACK: 200`을 확인합니다.
   ACK는 다음 네트워크 조회 주기에 전송되므로 LCD 출력과 동시에 로그가 나오지 않을 수 있습니다.
7. 팀장으로 회차 목록을 조회하여 **display_ack=true**를 확인합니다. 장치 목록의 last_ack도 시각으로 갱신됩니다.
8. 승인된 팀원 계정으로 로그인해 POST /api/attendance-sessions/S/check-in에 `{ "code": "실제6자리" }`를 보냅니다.
   이후 팀장 /records 조회와 TiDB AttendanceRecords에서 출석을 확인합니다.
9. 팀장이 종료하거나 5분이 지나면 LCD에서 이전 코드가 사라지고 Waiting...으로 돌아가야 합니다.
10. 새 회차에서 Wi-Fi를 끊어도 수신한 코드의 로컬 만료 시간에 화면이 지워지는지 확인합니다.
    Wi-Fi가 끊긴 동안 서버의 수동 종료는 알 수 없으므로 종료 즉시 화면이 바뀌지는 않습니다. 서버의 출석 판정은 즉시 종료됩니다.

hd44780_I2Cexp가 PCF8574/MCP23008 기반의 일반적인 I2C 백팩 주소와 핀 매핑을 자동 탐색합니다.
자동 탐지가 실패하면 라이브러리 예제 `ioClass → hd44780_I2Cexp → I2CexpDiag`로 진단할 수 있습니다.
주소를 확인한 경우 LCD_I2C_ADDRESS를 0x27 또는 실제 주소로 지정할 수 있습니다. 초기화 실패 후에는 배선을 확인하고 리셋합니다.
16×2라는 크기만으로 모든 컨트롤러가 같은 것은 아니므로 다른 방식의 I2C 컨트롤러라면 어댑터 조정이 필요합니다.

초기화나 LCD 쓰기에서 오류가 나면 ACK를 보내지 않고 Serial 수신은 계속합니다.
성공한 ACK는 LCD I/O가 성공했다는 응답입니다. 백라이트/대비 조절로 실제 글자가 보이는지도 사람이 확인합니다.
LCD 출력 이후 연결을 물리적으로 제거하는 상황을 지속 감시하는 기능은 포함하지 않습니다.

## 7. HTTPS 인증서

root_ca.h에는 공식 CA 사이트에서 받은 GTS Root R4와 ISRG Root X1 공개 루트 인증서가 있습니다.
2026-11-01에 이 루트로 현재 Render 호스트의 TLS 검증을 확인했습니다.
코드는 setCACert를 사용하고 setInsecure를 호출하지 않습니다.
Render의 인증기관이 바뀌면 공식 CA의 인증서로 갱신해야 할 수 있습니다.
시간 동기화/인증서 오류가 나면 원인을 확인하고 인증서 검증을 끄지 않습니다.

## 8. 오류 확인

| 상태 | 확인할 내용 |
| --- | --- |
| Wi-Fi 연결 실패 | SSID·비밀번호·지원 대역·공유기 인터넷 |
| 시간 동기화 대기 | 인터넷과 NTP 접근 |
| HTTPS 음수 오류 | 시간·CA 인증서·DNS·인터넷 |
| 401 | 장치 ID와 장치 원문 키 조합 |
| 404 | Render에 0.4.0 API가 배포되었는지 |
| 409 ACK | 이미 종료/만료되었거나 늦은 이전 회차 ACK |
| 코드 없음 | 해당 장치를 선택해 출석을 시작했는지 |
| display_ack=false | LCD_ENABLED=1인지, LCD ready/쓰기 성공 로그와 ACK HTTP 응답 |
| LCD initialization failed | SDA=21/SCL=22/GND와 실제 백팩 종류 확인 후 리셋; I2CexpDiag |
| LCD 백라이트만 켜짐 | 백팩의 대비 조절 가변저항과 배선 확인 |
| hd44780.h: No such file | Library Manager에서 hd44780 by Bill Perry 설치 |
| NetworkClientSecure.h: No such file | esp32 by Espressif Systems 3.x 및 ESP32 보드 선택 |

### HTTP 200만 반복되고 코드가 없을 때

HTTP 200은 응답 상태이며 출석 코드 JSON을 읽었다는 의미는 아닙니다.
2026-11-02-r2부터 기존에 조용히 건너뛰던 응답 형식/크기 오류도 Serial에 출력합니다.
진단 수정본도 ESP32 core 3.3.12 / ArduinoJson 7.4.3 / hd44780 1.3.2의 LCD 활성 설정으로 컴파일에 통과했습니다.
수정한 attendance_display.ino를 업로드한 뒤 EN/RESET을 누르면 시작 로그에서
`Attendance firmware: 2026-11-02-r3`와 실제 DEVICE_ID를 확인할 수 있습니다.
기존 config.h의 Wi-Fi와 장치 키는 유지합니다. 펌웨어만 수정한 경우 Render를 다시 배포할 필요는 없습니다.

1. 출석 시작 POST가 201이고 재시도가 409이면 활성 회차가 이미 있다는 뜻입니다. 같은 POST를 반복하지 않습니다.
2. Swagger의 **ESP32 장치 → 파란색 GET /api/devices/{device_id}/display**를 엽니다.
3. Authorize의 DeviceKey에 기기 원문 키를 넣고 device_id를 ESP32의 DEVICE_ID와 똑같이 입력해 실행합니다.
4. Response body의 session을 확인합니다. 이 GET은 새 회차를 만드는 요청이 아닙니다.

| Swagger 또는 Serial 결과 | 다음 확인 |
|---|---|
| GET display의 session=null | 해당 장치에 활성 회차가 없음. 시작한 팀/장치와 5분 만료 여부 확인 |
| GET display의 session에 id/code/expires_in 존재 | 서버에 코드는 있음. ESP32의 응답 수신/JSON 처리 로그 확인 |
| GET display가 401 | DeviceKey와 device_id 조합 확인; 사용자 접근 토큰을 DeviceKey에 넣지 않음 |
| Serial: Rejected HTTP 200: Content-Type=text/html | JSON 대신 HTML을 받음. API_BASE_URL과 실제 응답 페이지 확인 |
| Serial: Content-Type=<missing> | 응답 헤더를 확인할 수 없음. 사용 중인 ESP32 core 버전과 서버 응답 비교 |
| Serial: Rejected JSON / parse failed | 빈 응답·잘린 응답·응답 크기·JSON 오류 로그 확인 |
| Serial: no active attendance session for DEVICE_ID=... | 그 장치의 session=null. 서버의 회차와 장치 ID 확인 |
| Serial: Active session 뒤 Received attendance code | 수신/검증 성공. LCD와 ACK 단계로 진행 |

API_BASE_URL은 `https://swe-project-u3f0.onrender.com`입니다. /docs, /api, # 조각을 붙이지 않습니다.
장치 인증 401은 Render sleep이나 사용자 접근 토큰 30분 만료와 별개입니다. 장치 키 자체에는 현재 유효 기간이 없습니다.
Swagger 새로고침 후 인증 입력이 사라졌다면 DeviceKey에 config.h의 DEVICE_KEY 원문을 다시 넣습니다.
따옴표/Bearer 접두어/DB의 sha256: 해시를 넣지 않습니다. HTTPBearer에는 사용자 접근 토큰을 별도로 넣습니다.
정확한 원문 키를 잃어버렸다면 팀장으로 장치를 새로 등록하고 새 ID/키를 config.h에 함께 반영해 재업로드합니다.
같은 팀의 활성 출석 회차가 남아 있으면 먼저 종료하고 새 장치로 새 회차를 시작합니다. 계정과 모집글을 다시 만들 필요는 없습니다.
진단 로그는 응답 형식/크기/장치·회차 ID를 표시하며 인증키나 Wi-Fi 비밀번호는 출력하지 않습니다.
수신한 출석 코드는 기존처럼 Serial에 출력되므로 화면을 공유할 때 코드가 유효한 시간도 고려합니다.

### 회차가 OPEN인데 장치가 401일 때

OPEN은 팀장이 출석 회차를 만들었다는 상태입니다. 장치의 ID/키 인증 성공을 뜻하지 않습니다.
사진 예시의 post_id=60001은 팀 모집글, device_id=30002는 장치, id=3은 출석 회차입니다.
ESP32의 DEVICE_ID에는 30002를 넣고 DEVICE_KEY에는 **30002를 등록할 때 같은 응답에서 받은 device_credential**을 넣습니다.
이전 장치 1의 키를 그대로 두면 401입니다. 30002처럼 큰 ID도 정상적으로 사용할 수 있습니다.

1. 장치 등록 시 보관한 응답에서 같은 ID/키 쌍인지 확인합니다. 키를 채팅/GitHub에 공유하지 않습니다.
2. config.h의 DEVICE_ID/DEVICE_KEY를 둘 다 확인하고 .ino를 다시 업로드합니다. 파일 수정만으로 보드의 값은 바뀌지 않습니다.
3. Serial 시작 로그의 DEVICE_ID가 원하는 숫자인지 확인합니다.
4. Swagger DeviceKey에도 같은 키를 넣고 GET /api/devices/30002/display로 확인합니다.
5. 200 + session=null이면 인증은 성공했지만 활성 출석이 없습니다. 새 회차를 시작하고 5분 안에 다시 확인합니다.
6. 200 + session.code가 있으면 ESP32에서도 수신 코드와 LCD/ACK를 확인합니다.

같은 등록 응답을 잃었다면 GET 장치 목록으로 원문 키를 복구할 수는 없습니다.
팀장으로 장치를 새로 등록하고, 새 ID/키를 함께 저장합니다. 기존 회차는 종료하고 새 장치로 다시 출석을 시작합니다.
401을 피하려고 서버의 장치 인증을 제거하거나 DB 키를 평문으로 바꾸지 않습니다.
2026-11-02 분리된 API 테스트에서 OPEN 회차 + 장치 30002 + 이전 키는 401, 올바른 키는 코드 조회 200을 확인했습니다.
관련 출석·장치 테스트 22개가 통과했습니다. 실제 사용자 DB의 키는 읽거나 변경하지 않았습니다.
401 안내를 추가한 r3 펌웨어도 가짜 키/DEVICE_ID=30002/LCD 활성 설정으로 ESP32 컴파일에 통과했습니다.

### 팀장과 최초 장치 설정의 관계

팀장이 되었다고 장치 ID가 자동 발급되지는 않습니다. 본인 모집글의 POST /api/posts/{post_id}/devices를 호출해야 발급됩니다.
현재 구조의 장치는 한 모집글(팀)에 연결되며 등록할 때 ID/키가 만들어집니다.
장치 관리 담당자가 Wi-Fi와 ID/키를 config.h에 한 번 입력해 업로드하고, 같은 팀에서는 계속 재사용합니다.
팀장은 매회 웹에서 출석 시작/종료만 실행하면 됩니다. 새 출석 회차 ID는 펌웨어에 입력하지 않습니다.
Wi-Fi 변경, 장치 재등록, 다른 팀으로의 변경처럼 설정이 바뀌는 경우에만 수정·재업로드합니다.
웹 설정 화면/USB Serial 입력/NVS 저장을 이용해 코드 편집 없는 설정 방식으로 확장할 수 있지만, 현재 예제에는 포함하지 않았습니다.
시연 범위에서는 한 팀과 한 ESP32의 설정을 유지하는 방식으로 진행할 수 있습니다.

### config.h 보관과 시연

config.h는 실제 Wi-Fi 비밀번호와 기기 인증키가 들어 있는 개인 설정입니다. GitHub에는 올리지 않습니다.
attendance_display/.gitignore에서 제외하며 config.example.h에는 빈 값과 공개 기본 설정만 공유합니다.
시연할 노트북의 스케치 폴더에 config.h를 유지하고, 다른 PC로 옮기면 같은 폴더에 별도로 준비합니다.
시연 장소의 Wi-Fi가 달라지면 SSID/비밀번호를 수정해 다시 업로드합니다. 같은 설정이면 재업로드할 필요는 없습니다.

기기 키나 Wi-Fi 비밀번호를 채팅/스크린샷/공개 GitHub에 올리지 않습니다.
Swagger 및 실제 DB 확인은 [출석 API 안내](../backend/docs/attendance-and-esp32.md)를 참고하세요.

참고: [Espressif Wi-Fi API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html),
[공식 HTTPS 예제](https://github.com/espressif/arduino-esp32/blob/master/libraries/HTTPClient/examples/BasicHttpsClient/BasicHttpsClient.ino),
[ArduinoJson 7](https://arduinojson.org/v7/api/jsondocument/),
[Espressif I2C 설정](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/i2c.html),
[hd44780 라이브러리·자동 탐지·오류 반환](https://github.com/duinoWitchery/hd44780).
