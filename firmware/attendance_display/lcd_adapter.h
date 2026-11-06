#pragma once
#include <Arduino.h>

// Defaults also support an existing config.h created before LCD settings existed.
#ifndef LCD_ENABLED
#define LCD_ENABLED 0
#endif
#ifndef LCD_SDA_PIN
#define LCD_SDA_PIN 21
#endif
#ifndef LCD_SCL_PIN
#define LCD_SCL_PIN 22
#endif
#ifndef LCD_I2C_ADDRESS
#define LCD_I2C_ADDRESS 0
#endif

#if LCD_ENABLED
#include <Wire.h>
#include <hd44780.h>
#include <hd44780ioClass/hd44780_I2Cexp.h>

namespace attendance_lcd {
static hd44780_I2Cexp lcd(LCD_I2C_ADDRESS);
static bool ready = false;

inline bool writeLine(uint8_t row, const char *text) {
  char padded[16];
  memset(padded, ' ', sizeof(padded));
  memcpy(padded, text, min(strlen(text), sizeof(padded)));
  if (lcd.setCursor(0, row) != 0 ||
      lcd.write(reinterpret_cast<const uint8_t *>(padded), sizeof(padded)) != sizeof(padded)) {
    ready = false;
    Serial.println("LCD write failed; ACK withheld. Check wiring and reset ESP32.");
    return false;
  }
  return true;
}
}  // namespace attendance_lcd
#endif

inline void setupLcd() {
#if LCD_ENABLED
  using namespace attendance_lcd;
  // hd44780.begin() calls Wire.begin(); set the pins BEFORE that call.
  if (!Wire.setPins(LCD_SDA_PIN, LCD_SCL_PIN)) {
    Serial.println("LCD I2C pin setup failed; ACK withheld.");
    return;
  }
  Wire.setTimeOut(50);
  const int status = lcd.begin(16, 2);  // Auto-detect address/backpack mapping, enable backlight.
  ready = status == 0;
  if (!ready) {
    Serial.printf("LCD initialization failed: %d; ACK withheld. Check wiring and reset ESP32.\n", status);
    return;
  }
  Serial.printf("LCD ready: 16x2, SDA=%d, SCL=%d, address=0x%02X\n",
                LCD_SDA_PIN, LCD_SCL_PIN, static_cast<unsigned int>(lcd.getProp(hd44780_I2Cexp::Prop_addr)));
#else
  Serial.println("Serial-only mode (LCD_ENABLED=0); LCD disabled, ACK withheld.");
#endif
}

inline bool showAttendanceCode(const char *code) {
  // Keep leading zeros and reject malformed input even when called independently.
  if (!code || strlen(code) != 6) return false;
  for (size_t i = 0; i < 6; ++i) if (code[i] < '0' || code[i] > '9') return false;
#if LCD_ENABLED
  using namespace attendance_lcd;
  if (!ready) return false;
  char secondRow[17];
  snprintf(secondRow, sizeof(secondRow), "Code: %s", code);
  if (!writeLine(0, "Attendance code") || !writeLine(1, secondRow)) return false;
  Serial.println("LCD code written; queuing display ACK.");
  // This reports successful LCD I/O, not a physical/visual verification of pixels.
  return true;
#else
  return false;
#endif
}

inline void clearLcdCode() {
#if LCD_ENABLED
  using namespace attendance_lcd;
  if (ready && writeLine(0, "Attendance")) writeLine(1, "Waiting...");
#endif
  Serial.println("Attendance display: IDLE (closed, expired, or no active session)");
}
