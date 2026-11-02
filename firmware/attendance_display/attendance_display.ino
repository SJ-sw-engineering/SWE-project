#include <Arduino.h>
#include <WiFi.h>
#include <NetworkClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>

#if __has_include("config.h")
#include "config.h"
#else
#include "config.example.h"
#endif
#include "root_ca.h"
#include "lcd_adapter.h"

struct DisplayMessage {
  uint32_t sessionId;
  uint32_t deadlineMs;
  char code[7];
};

QueueHandle_t displayQueue;
QueueHandle_t ackQueue;
bool configured = false;

// Network calls run separately so LCD expiry still works during a timeout/offline.
bool httpRequest(const String &path, const String &body, String *responseBody) {
  NetworkClientSecure tls;
  tls.setCACert(RENDER_ROOT_CA);  // Certificate and host verification remain enabled.
  tls.setHandshakeTimeout(10);
  HTTPClient http;
  http.setConnectTimeout(10000);
  http.setTimeout(15000);
  http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
  if (!http.begin(tls, String(API_BASE_URL) + path)) return false;
  const char *headers[] = {"Content-Type"};
  http.collectHeaders(headers, 1);
  http.addHeader("Accept", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  int status;
  if (body.length()) {
    http.addHeader("Content-Type", "application/json");
    status = http.POST(body);
  } else {
    status = http.GET();
  }
  Serial.printf("HTTPS %s: %d\n", body.length() ? "ACK" : "display", status);
  bool ok = status == 200 && http.header("Content-Type").startsWith("application/json");
  if (ok && responseBody) {
    if (http.getSize() > 4096) ok = false;
    else *responseBody = http.getString();
  }
  if (status == 401 || status == 403 || status == 404) {
    DisplayMessage idle = {};
    xQueueOverwrite(displayQueue, &idle);
  }
  http.end();
  return ok;
}

void networkTask(void *) {
  uint32_t nextPollMs = 0;
  uint32_t nextReconnectMs = 0;
  uint32_t pendingAck = 0;
  bool ntpStarted = false;
  bool timeReadyLogged = false;
  for (;;) {
    if (WiFi.status() != WL_CONNECTED) {
      if (static_cast<int32_t>(millis() - nextReconnectMs) >= 0) {
        Serial.println("Wi-Fi reconnecting...");
        WiFi.reconnect();
        nextReconnectMs = millis() + 10000;
      }
      vTaskDelay(pdMS_TO_TICKS(500));
      continue;
    }
    if (!ntpStarted) {
      configTime(0, 0, "pool.ntp.org", "time.google.com");
      ntpStarted = true;
      Serial.println("Wi-Fi connected. Synchronizing time for HTTPS.");
    }
    if (time(nullptr) < 1700000000) {
      vTaskDelay(pdMS_TO_TICKS(500));
      continue;
    }
    if (!timeReadyLogged) {
      Serial.println("Time synchronized. Starting HTTPS polling.");
      timeReadyLogged = true;
    }
    uint32_t confirmed;
    if (xQueueReceive(ackQueue, &confirmed, 0) == pdTRUE) pendingAck = confirmed;
    if (static_cast<int32_t>(millis() - nextPollMs) < 0) {
      vTaskDelay(pdMS_TO_TICKS(50));
      continue;
    }
    const String devicePath = String("/api/devices/") + DEVICE_ID;
    const uint32_t requestStartedMs = millis();
    String payload;
    unsigned int pollSeconds = 10;
    if (httpRequest(devicePath + "/display", "", &payload)) {
      JsonDocument document;
      const DeserializationError jsonError = deserializeJson(document, payload);
      if (!jsonError && !document["session"].isUnbound()) {
        DisplayMessage message = {};
        bool valid = true;
        if (!document["session"].isNull()) {
          JsonObject session = document["session"].as<JsonObject>();
          const char *code = session["code"] | "";
          const long expiresIn = session["expires_in"] | 0L;
          valid = session["id"].is<uint32_t>() && session["id"].as<uint32_t>() > 0
               && strlen(code) == 6 && expiresIn > 0 && expiresIn <= 300;
          for (size_t i = 0; valid && i < 6; ++i) valid = code[i] >= '0' && code[i] <= '9';
          if (valid) {
            message.sessionId = session["id"].as<uint32_t>();
            memcpy(message.code, code, 7);
            // Conservatively subtract total network latency; never extend TTL on a retry.
            message.deadlineMs = requestStartedMs + static_cast<uint32_t>(expiresIn) * 1000;
            if (static_cast<int32_t>(millis() - message.deadlineMs) >= 0) message.sessionId = 0;
            pollSeconds = 2;
          }
        } else {
          Serial.println("Server: no active attendance session.");
        }
        if (valid) {
          xQueueOverwrite(displayQueue, &message);
          if (message.sessionId == 0) pendingAck = 0;
          else if (pendingAck && pendingAck != message.sessionId) pendingAck = 0;
        } else {
          Serial.println("Invalid attendance session data; ignoring response.");
        }
      } else {
        Serial.println("Invalid display JSON or missing session field; ignoring response.");
      }
    }
    if (pendingAck) {
      String body = String("{\"session_id\":") + pendingAck + "}";
      if (httpRequest(devicePath + "/ack", body, nullptr)) pendingAck = 0;
    }
    nextPollMs = millis() + pollSeconds * 1000;
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

void setup() {
  Serial.begin(115200);
  setupLcd();
  clearLcdCode();
  configured = strlen(WIFI_SSID) && strlen(DEVICE_KEY) && DEVICE_ID > 0
            && String(API_BASE_URL).startsWith("https://");
  if (!configured) {
    Serial.println("Copy config.example.h to config.h and set Wi-Fi, DEVICE_ID and DEVICE_KEY.");
    return;
  }
  displayQueue = xQueueCreate(1, sizeof(DisplayMessage));
  ackQueue = xQueueCreate(1, sizeof(uint32_t));
  if (!displayQueue || !ackQueue) {
    configured = false;
    Serial.println("Queue allocation failed.");
    return;
  }
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  if (xTaskCreate(networkTask, "attendance_https", 12288, nullptr, 1, nullptr) != pdPASS) {
    configured = false;
    Serial.println("Network task creation failed.");
  }
}

void loop() {
  static DisplayMessage current = {};
  static bool lcdWritten = false;
  if (configured) {
    DisplayMessage received;
    if (xQueueReceive(displayQueue, &received, 0) == pdTRUE) {
      if (received.sessionId == 0) {
        if (current.sessionId) clearLcdCode();
        current = {};
        lcdWritten = false;
      } else {
        if (current.sessionId != received.sessionId || strcmp(current.code, received.code) != 0) {
          lcdWritten = false;
          Serial.print("Received attendance code: ");
          Serial.println(received.code);
        }
        current = received;
        if (!lcdWritten && static_cast<int32_t>(millis() - current.deadlineMs) < 0) {
          lcdWritten = showAttendanceCode(current.code);
          // A slow LCD I/O must not acknowledge a code that expired during the write.
          if (lcdWritten && static_cast<int32_t>(millis() - current.deadlineMs) < 0) {
            xQueueOverwrite(ackQueue, &current.sessionId);
          }
        }
      }
    }
    if (current.sessionId && static_cast<int32_t>(millis() - current.deadlineMs) >= 0) {
      clearLcdCode();
      current = {};
      lcdWritten = false;
    }
  }
  delay(20);
}
