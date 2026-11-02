#include <Arduino.h>
#include <WiFi.h>
#include <NetworkClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <esp_arduino_version.h>
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
  if (!http.begin(tls, String(API_BASE_URL) + path)) {
    Serial.println("HTTPS initialization failed; check API_BASE_URL (HTTPS origin only).");
    return false;
  }
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
  if (status == 401) {
    Serial.printf("Device authentication failed for DEVICE_ID=%u.\n", DEVICE_ID);
    Serial.println("DEVICE_ID and DEVICE_KEY must come from the SAME device registration response.");
    Serial.println("Changing DEVICE_ID alone is not enough. Update both values and upload again.");
    Serial.println("An OPEN attendance session does not replace device authentication.");
  }
  String contentType = http.header("Content-Type");
  contentType.trim();
  // Media type tokens are case-insensitive; parameters such as charset are allowed.
  String mediaType = contentType;
  const int parameter = mediaType.indexOf(';');
  if (parameter >= 0) mediaType = mediaType.substring(0, parameter);
  mediaType.trim();
  mediaType.toLowerCase();
  bool ok = status == 200 && mediaType == "application/json";
  if (status == 200 && !ok) {
    Serial.printf("Rejected HTTP 200: Content-Type=%s; expected application/json.\n",
                  contentType.length() ? contentType.c_str() : "<missing>");
    Serial.println("Check API_BASE_URL: use the server origin, without /docs, /api or extra paths.");
  } else if (status < 0) {
    Serial.printf("HTTPS transport error: %s\n", HTTPClient::errorToString(status).c_str());
  }
  if (ok && responseBody) {
    const int expectedSize = http.getSize();
    if (expectedSize > 4096) {
      Serial.printf("Rejected JSON: Content-Length=%d exceeds 4096 bytes.\n", expectedSize);
      ok = false;
    } else {
      *responseBody = http.getString();
      const unsigned int receivedSize = responseBody->length();
      Serial.printf("Display JSON: %u bytes (Content-Length=%d).\n", receivedSize, expectedSize);
      if (!receivedSize || receivedSize > 4096 ||
          (expectedSize >= 0 && receivedSize != static_cast<unsigned int>(expectedSize))) {
        Serial.println("Rejected JSON: empty, oversized or incomplete response body.");
        ok = false;
      }
    }
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
          Serial.printf("Server: no active attendance session for DEVICE_ID=%u.\n", DEVICE_ID);
        }
        if (valid) {
          if (message.sessionId) {
            Serial.printf("Active session: id=%lu, DEVICE_ID=%u, remaining=%lu ms.\n",
                          static_cast<unsigned long>(message.sessionId), DEVICE_ID,
                          static_cast<unsigned long>(message.deadlineMs - millis()));
          }
          xQueueOverwrite(displayQueue, &message);
          if (message.sessionId == 0) pendingAck = 0;
          else if (pendingAck && pendingAck != message.sessionId) pendingAck = 0;
        } else {
          Serial.println("Invalid attendance session: expected positive id, 6 digit string code and 1..300 expires_in.");
        }
      } else {
        if (jsonError) Serial.printf("Display JSON parse failed: %s\n", jsonError.c_str());
        else Serial.println("Display JSON is missing the session field; check the API endpoint/deployment.");
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
  Serial.printf("Attendance firmware: 2026-11-02-r3; Arduino-ESP32 %s; DEVICE_ID=%u\n",
                ESP_ARDUINO_VERSION_STR, DEVICE_ID);
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
