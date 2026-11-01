#pragma once
#include <Arduino.h>

// Replace ONLY these three functions with the LCD code that worked on your board.
// Model, library, I2C address and pins have not been confirmed; no pin is assumed.
inline void setupLcd() {
  Serial.println("LCD adapter is not configured yet. Network/Serial test mode.");
}

inline bool showAttendanceCode(const char *code) {
  static String previous;
  if (previous != code) {
    Serial.print("Received attendance code: ");
    Serial.println(code);
    Serial.println("LCD ACK withheld: implement showAttendanceCode and return true after printing to LCD.");
    previous = code;
  }
  // Insert your LCD clear/setCursor/print calls here.
  // Return true only after the code was actually written to your LCD.
  return false;
}

inline void clearLcdCode() {
  // Insert your LCD clear/IDLE calls here.
  Serial.println("Attendance display: IDLE (closed, expired, or no active session)");
}
