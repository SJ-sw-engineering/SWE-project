# ESP32 → Wi-Fi → Render 출석 코드 표시

Arduino IDE용 스케치: `attendance_display/attendance_display.ino`.
현재 사용자의 LCD 예제는 나중에 제공받기로 했으므로 LCD 출력 코드는 어댑터에 연결하도록 작성했습니다.
기본 예제는 Serial로 코드 수신을 확인하며, LCD를 구성하기 전에는 표시 완료 ACK를 전송하지 않습니다.

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
POST /api/posts/{팀ID}/devices를 실행하고 응답의 id와 device_credential을 기록합니다.
DB에 저장된 해시가 아니라 이 응답에서 받은 원문 키를 사용합니다.

## 3. Arduino IDE 준비

1. Boards Manager에서 Espressif의 esp32 보드 패키지를 준비합니다. 예제는 Arduino ESP32 3.x API를 사용합니다.
2. Library Manager에서 Benoit Blanchon의 ArduinoJson 7.x를 설치합니다.
3. attendance_display.ino를 엽니다. 같은 폴더의 헤더 파일도 스케치와 함께 유지합니다.
4. 현재 사용 중인 실제 ESP32 보드와 포트를 선택합니다.
5. Serial Monitor 속도는 115200입니다.

검증에 사용한 구성은 ESP32 core 3.3.12, ArduinoJson 7.4.3, 일반 ESP32 Dev Module입니다.
빈 기본 설정과 임시 테스트 설정 두 경우 모두 컴파일에 통과했습니다. 통신 코드 전체 포함 빌드는 프로그램 영역 약 78%를 사용했습니다.
테스트 설정에는 실제 Wi-Fi/장치 키를 사용하지 않았고 업로드하지 않았습니다.
사용자 보드 모델은 확정하지 않았으므로 업로드 시에는 LCD 시험에 성공했던 보드/포트 설정을 사용합니다.

## 4. Wi-Fi와 장치 키 입력

config.example.h를 같은 폴더의 config.h로 복사합니다. config.h는 Git에서 제외됩니다.

```cpp
static const char WIFI_SSID[] = "공유기 또는 핫스팟 이름";
static const char WIFI_PASSWORD[] = "Wi-Fi 비밀번호";
static const char API_BASE_URL[] = "https://swe-project-u3f0.onrender.com";
static const unsigned int DEVICE_ID = 1; // 실제 장치 등록 응답 ID
static const char DEVICE_KEY[] = "esp_장치등록응답에서받은키";
```

예시 값은 본인 값으로 바꿉니다. API 주소 끝에 /docs나 /api를 붙이지 않습니다.
먼저 일반 ESP32 Dev Module에서 사용할 수 있는 2.4GHz 개인 공유기 또는 호환되는 휴대폰 핫스팟으로 시험하면 됩니다.
학교의 브라우저 로그인/기업 인증 Wi-Fi는 이 SSID·비밀번호 예제만으로 연결되지 않을 수 있습니다.
DEVICE_KEY는 사용자 로그인 토큰, JWT 비밀키, DB 비밀번호, Google 계정 비밀번호와 별개입니다.

코드는 WiFi.begin으로 접속하고 연결이 끊기면 재연결을 시도합니다.
인터넷 시간 동기화가 끝난 뒤 HTTPS를 호출합니다. 네트워크에서 NTP가 차단되면 시간 동기화 단계에서 멈출 수 있습니다.

## 5. Serial에서 네트워크부터 확인

1. 업로드 후 Serial Monitor에서 Wi-Fi 연결과 시간 동기화 메시지를 확인합니다.
2. HTTPS display: 200이면 서버에 연결된 것입니다. 대기 중에는 session=null이므로 코드가 표시되지 않습니다.
3. Swagger에서 해당 팀과 장치 ID로 출석을 시작합니다.
4. Serial에 Received attendance code: 000047와 같은 숫자 6자리가 출력되는지 확인합니다. 실제 코드는 매 회차 서버가 생성합니다.
5. 기본 LCD 어댑터는 ACK withheld를 출력합니다. 이 상태가 정상이며 LCD 표시를 완료했다고 서버에 보고하지 않습니다.

활성 회차는 약 2초, 대기 상태는 약 10초 간격으로 조회합니다.
네트워크 작업을 별도 태스크로 수행하므로 HTTPS 연결이 지연되어도 메인 루프의 표시 만료 처리는 계속됩니다.
사용자 JWT는 보내지 않고 X-Device-Key 헤더만 보냅니다.

## 6. 나중에 LCD 코드 연결

lcd_adapter.h의 세 함수를 LCD 예제에 맞게 구현합니다.

```cpp
void setupLcd();                       // 성공했던 라이브러리/주소/핀으로 초기화
bool showAttendanceCode(const char*); // LCD에 출력한 후 true 반환
void clearLcdCode();                   // 만료/종료 시 지우거나 IDLE 표시
```

showAttendanceCode가 true를 반환하면 네트워크 태스크가 해당 회차 ID로 ACK를 전송합니다.
단순히 return false를 true로 바꾸는 것으로 실제 LCD 출력이 구현되지는 않습니다. LCD print 호출을 연결한 뒤 true를 반환합니다.
라이브러리에 따라 실제 액정 표시까지 읽어 확인할 수는 없으므로 ACK는 펌웨어가 출력 명령을 수행했다는 응답입니다.
실제 화면이 보이는지도 사람이 확인합니다.

연결 후 확인 순서는 출석 시작 → LCD 코드 확인 → 팀장 화면 display_ack=true → 팀원 코드 입력 → 출석 이력입니다.
출석 종료 또는 만료 시 대기 화면으로 바뀌는지, Wi-Fi를 끊어도 기존 코드가 로컬 만료 시간에 지워지는지 확인합니다.

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
| display_ack=false | LCD 어댑터 구성과 실제 출력 함수 반환값 |

기기 키나 Wi-Fi 비밀번호를 채팅/스크린샷/공개 GitHub에 올리지 않습니다.
Swagger 및 실제 DB 확인은 [출석 API 안내](../backend/docs/attendance-and-esp32.md)를 참고하세요.

참고: [Espressif Wi-Fi API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html),
[공식 HTTPS 예제](https://github.com/espressif/arduino-esp32/blob/master/libraries/HTTPClient/examples/BasicHttpsClient/BasicHttpsClient.ino),
[ArduinoJson 7](https://arduinojson.org/v7/api/jsondocument/).
