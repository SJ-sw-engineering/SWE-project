#pragma once

// Copy to config.h and fill locally. config.h is ignored by Git.
static const char WIFI_SSID[] = "";
static const char WIFI_PASSWORD[] = "";
static const char API_BASE_URL[] = "https://swe-project-u3f0.onrender.com";
static const unsigned int DEVICE_ID = 0;  // id returned by POST /api/posts/{id}/devices
static const char DEVICE_KEY[] = "";     // device_credential returned ONCE by that API

// First test: 0 = Serial only, no LCD ACK. Then set 1 and upload again.
#define LCD_ENABLED 0
#define LCD_SDA_PIN 21
#define LCD_SCL_PIN 22
// 0 auto-detects a supported PCF8574/MCP23008 backpack; e.g. 0x27 fixes its address.
#define LCD_I2C_ADDRESS 0
