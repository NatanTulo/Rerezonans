#include <Adafruit_PWMServoDriver.h>
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Wire.h>

// ========= Hardware config =========
static const uint8_t I2C_SDA_PIN = 21;
static const uint8_t I2C_SCL_PIN = 22;
static const uint8_t PCA9685_ADDR = 0x40;

// 5 DOF: 3x MG996R (ch 0..2), 2x MG90S (ch 3..4)
static const uint8_t NUM_SERVOS = 5;
static const uint8_t SERVO_CH[NUM_SERVOS] = {0, 1, 2, 3, 4};

// All servos = 1.0–2.0 ms at 50 Hz, center 1.5 ms.
// Angle convention: -90..+90 deg.
struct ServoConfig {
  uint16_t min_us;   // at -90 deg
  uint16_t max_us;   // at +90 deg
  int16_t offset_us; // trim around center
  bool invert;       // invert direction
};

// Defaults
ServoConfig servoCfg[NUM_SERVOS] = {
    {1000, 2000, 0, false}, // ch 0 (MG996R)
    {1000, 2000, 0, false}, // ch 1 (MG996R)
    {1000, 2000, 0, false}, // ch 2 (MG996R)
    {1000, 2000, 0, false}, // ch 3 (MG90S)
    {1000, 2000, 0, false}, // ch 4 (MG90S)
};

// LED (use transistor/MOSFET). Pick a safe pin.
static const int LED_PIN = 16;
static const int LEDC_CH = 0;
static const int LEDC_FREQ = 1000; // 1 kHz
static const int LEDC_RES = 8;     // 0..255

// Servo frequency
static float SERVO_HZ = 50.0f;

// ========= Internals =========
Adafruit_PWMServoDriver pca = Adafruit_PWMServoDriver(PCA9685_ADDR);

// Current/start/target angles in degrees (-90..+90)
float currDeg[NUM_SERVOS] = {0, 0, 0, 0, 0};
float startDeg[NUM_SERVOS] = {0, 0, 0, 0, 0};
float targetDeg[NUM_SERVOS] = {0, 0, 0, 0, 0};

uint8_t currLed = 0, startLed = 0, targetLed = 0;

bool moving = false;
uint32_t moveStartMs = 0;
uint32_t moveDurMs = 0;

static const uint32_t UPDATE_DT_MS = 15;
uint32_t lastUpdateMs = 0;

static const size_t RX_BUF_SZ = 512;
char rxBuf[RX_BUF_SZ];
size_t rxLen = 0;

// Reusable JSON documents (ArduinoJson 7+: use JsonDocument)
JsonDocument rxDoc;
JsonDocument txDoc;

// ========= Helpers =========
uint16_t usToTick(uint16_t us, float freqHz) {
  float period_us = 1000000.0f / freqHz;
  float tick = (us * 4096.0f) / period_us;
  if (tick < 0) tick = 0;
  if (tick > 4095) tick = 4095;
  return (uint16_t)(tick + 0.5f);
}

uint16_t angleToUs(uint8_t idx, float deg) {
  const ServoConfig &cfg = servoCfg[idx];
  // Clamp to -90..+90
  float d = deg;
  if (d < -90.0f) d = -90.0f;
  if (d > +90.0f) d = +90.0f;

  // Map -90..+90 to 0..1
  float t = (d + 90.0f) / 180.0f; // -90->0, 0->0.5, +90->1

  if (cfg.invert) t = 1.0f - t;

  float usf = cfg.min_us + t * (cfg.max_us - cfg.min_us);
  int32_t us = (int32_t)(usf + 0.5f) + cfg.offset_us;

  // Safety clamp
  if (us < 800) us = 800;
  if (us > 2200) us = 2200;

  return (uint16_t)us;
}

void writeServoDeg(uint8_t idx, float deg) {
  uint8_t ch = SERVO_CH[idx];
  uint16_t us = angleToUs(idx, deg);
  uint16_t tick = usToTick(us, SERVO_HZ);
  pca.setPWM(ch, 0, tick);
}

void applyAllOutputs() {
  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    writeServoDeg(i, currDeg[i]);
  }
  ledcWrite(LEDC_CH, currLed);
}

void startMove(const float *deg, uint32_t durationMs, uint8_t ledVal) {
  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    startDeg[i] = currDeg[i];
    targetDeg[i] = deg[i];
  }
  startLed = currLed;
  targetLed = ledVal;
  moveStartMs = millis();
  moveDurMs = max<uint32_t>(1, durationMs);
  moving = true;
}

void updateMotion() {
  uint32_t now = millis();
  if (!moving) return;

  float t = (float)(now - moveStartMs) / (float)moveDurMs;
  if (t >= 1.0f) {
    for (uint8_t i = 0; i < NUM_SERVOS; i++) currDeg[i] = targetDeg[i];
    currLed = targetLed;
    moving = false;
    applyAllOutputs();
    return;
  }

  // Linear interpolation
  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    currDeg[i] = startDeg[i] + (targetDeg[i] - startDeg[i]) * t;
  }
  currLed = (uint8_t)(startLed + (int)(targetLed - startLed) * t);

  if (now - lastUpdateMs >= UPDATE_DT_MS) {
    lastUpdateMs = now;
    applyAllOutputs();
  }
}

void setLed(uint8_t val) {
  targetLed = val;
  currLed = val;
  ledcWrite(LEDC_CH, val);
}

void setPwmFreq(float hz) {
  SERVO_HZ = hz;
  pca.setPWMFreq(SERVO_HZ);
  delay(10);
}

// ========= JSON helpers =========
void sendOk() {
  txDoc.clear();
  txDoc["ok"] = true;
  serializeJson(txDoc, Serial);
  Serial.write('\n');
}

void sendError(const char *msg) {
  txDoc.clear();
  txDoc["ok"] = false;
  txDoc["err"] = msg;
  serializeJson(txDoc, Serial);
  Serial.write('\n');
}

void handleJsonLine(const char *line) {
  rxDoc.clear();
  DeserializationError err = deserializeJson(rxDoc, line);
  if (err) {
    sendError("bad_json");
    return;
  }

  const char *cmd = rxDoc["cmd"] | "";

  if (strcmp(cmd, "ping") == 0) {
    txDoc.clear();
    txDoc["pong"] = true;
    serializeJson(txDoc, Serial);
    Serial.write('\n');
    return;
  }

  if (strcmp(cmd, "home") == 0) {
    float d[NUM_SERVOS];
    for (uint8_t i = 0; i < NUM_SERVOS; i++) d[i] = 0.0f; // center (1.5 ms)
    uint32_t ms = rxDoc["ms"] | 800;
    uint8_t ledVal = rxDoc["led"] | currLed;
    startMove(d, ms, ledVal);
    sendOk();
    return;
  }

  if (strcmp(cmd, "led") == 0) {
    int v = rxDoc["val"] | -1;
    if (v < 0 || v > 255) {
      sendError("led_range_0_255");
      return;
    }
    setLed((uint8_t)v);
    sendOk();
    return;
  }

  if (strcmp(cmd, "freq") == 0) {
    // Keep 50 Hz for servos. Range check anyway.
    float hz = rxDoc["hz"] | 50.0f;
    if (hz < 40.0f || hz > 60.0f) {
      sendError("freq_out_of_range_40_60");
      return;
    }
    setPwmFreq(hz);
    sendOk();
    return;
  }

  if (strcmp(cmd, "config") == 0) {
    int ch = rxDoc["ch"] | -1;
    if (ch < 0 || ch >= (int)NUM_SERVOS) {
      sendError("bad_ch");
      return;
    }
    if (!rxDoc["min_us"].isNull())
      servoCfg[ch].min_us = rxDoc["min_us"].as<uint16_t>();
    if (!rxDoc["max_us"].isNull())
      servoCfg[ch].max_us = rxDoc["max_us"].as<uint16_t>();
    if (!rxDoc["offset_us"].isNull())
      servoCfg[ch].offset_us = rxDoc["offset_us"].as<int16_t>();
    if (!rxDoc["invert"].isNull())
      servoCfg[ch].invert = rxDoc["invert"].as<bool>();
    sendOk();
    return;
  }

  if (strcmp(cmd, "frame") == 0) {
    // "deg" expects -90..+90 for each joint. Missing values = hold.
    JsonArray arr = rxDoc["deg"].as<JsonArray>();
    if (arr.isNull() || arr.size() == 0) {
      sendError("missing_deg");
      return;
    }
    float d[NUM_SERVOS];
    for (uint8_t i = 0; i < NUM_SERVOS; i++) {
      d[i] = (i < arr.size()) ? (float)arr[i].as<float>() : currDeg[i];
    }
    uint32_t ms = rxDoc["ms"] | 100;
    int ledVal = rxDoc["led"] | currLed;
    if (ledVal < 0) ledVal = currLed;
    startMove(d, ms, (uint8_t)ledVal);
    sendOk();
    return;
  }

  sendError("unknown_cmd");
}

void handleSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      rxBuf[rxLen] = '\0';
      if (rxLen > 0) {
        handleJsonLine(rxBuf);
      }
      rxLen = 0;
    } else {
      if (rxLen + 1 < RX_BUF_SZ) {
        rxBuf[rxLen++] = c;
      } else {
        // overflow – reset buffer
        rxLen = 0;
      }
    }
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(5);

  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN, 400000); // 400 kHz
  pca.begin();
  setPwmFreq(SERVO_HZ); // 50 Hz

  ledcSetup(LEDC_CH, LEDC_FREQ, LEDC_RES);
  ledcAttachPin(LED_PIN, LEDC_CH);
  setLed(0);

  // Initialize outputs at center (0 deg -> 1.5 ms)
  applyAllOutputs();

  txDoc.clear();
  txDoc["ready"] = true;
  txDoc["servos"] = NUM_SERVOS;
  serializeJson(txDoc, Serial);
  Serial.write('\n');
  // Debug marker to help diagnose serial encoding/baud problems.
  Serial.println("DEBUG:READY");
}

void loop() {
  handleSerial();
  updateMotion();
}