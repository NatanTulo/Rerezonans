#include <Adafruit_PWMServoDriver.h>
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <WiFi.h>
#include <WebSocketsServer.h>
#include <Adafruit_NeoPixel.h>

// ========= Hardware config =========
static const uint8_t I2C_SDA_PIN = 21;
static const uint8_t I2C_SCL_PIN = 22;
static const uint8_t PCA9685_ADDR = 0x40;

// WiFi hotspot config
const char* AP_SSID = "ESP32_RoboArm";
const char* AP_PASS = "roboarm123";
IPAddress AP_IP(192, 168, 4, 1);
IPAddress AP_GATEWAY(192, 168, 4, 1);
IPAddress AP_SUBNET(255, 255, 255, 0);

// WebSocket server
static const uint16_t WS_PORT = 81;

// RGB LED (adresowalna - NeoPixel)
static const uint8_t RGB_LED_PIN = 17;
static const uint8_t RGB_LED_COUNT = 1;  // jedna dioda, można zwiększyć

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
WebSocketsServer webSocket = WebSocketsServer(WS_PORT);
Adafruit_NeoPixel rgbLed(RGB_LED_COUNT, RGB_LED_PIN, NEO_GRB + NEO_KHZ800);

// Current/start/target angles in degrees (-90..+90)
float currDeg[NUM_SERVOS] = {0, 0, 0, 0, 0};
float startDeg[NUM_SERVOS] = {0, 0, 0, 0, 0};
float targetDeg[NUM_SERVOS] = {0, 0, 0, 0, 0};

uint8_t currLed = 0, startLed = 0, targetLed = 0;

// RGB LED state
uint8_t currR = 0, currG = 0, currB = 0;
uint8_t startR = 0, startG = 0, startB = 0;
uint8_t targetR = 0, targetG = 0, targetB = 0;

bool moving = false;
uint32_t moveStartMs = 0;
uint32_t moveDurMs = 0;

static const uint32_t UPDATE_DT_MS = 15;
uint32_t lastUpdateMs = 0;

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
  
  // Update RGB LED
  rgbLed.setPixelColor(0, rgbLed.Color(currR, currG, currB));
  rgbLed.show();
}

void startMove(const float *deg, uint32_t durationMs, uint8_t ledVal, uint8_t r = 255, uint8_t g = 255, uint8_t b = 255) {
  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    startDeg[i] = currDeg[i];
    targetDeg[i] = deg[i];
  }
  startLed = currLed;
  targetLed = ledVal;
  
  startR = currR;
  startG = currG;
  startB = currB;
  targetR = r;
  targetG = g;
  targetB = b;
  
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
    currR = targetR;
    currG = targetG;
    currB = targetB;
    moving = false;
    applyAllOutputs();
    return;
  }

  // Linear interpolation
  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    currDeg[i] = startDeg[i] + (targetDeg[i] - startDeg[i]) * t;
  }
  currLed = (uint8_t)(startLed + (int)(targetLed - startLed) * t);
  
  // RGB interpolation
  currR = (uint8_t)(startR + (int)(targetR - startR) * t);
  currG = (uint8_t)(startG + (int)(targetG - startG) * t);
  currB = (uint8_t)(startB + (int)(targetB - startB) * t);

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

void setRgbLed(uint8_t r, uint8_t g, uint8_t b) {
  targetR = r;
  targetG = g;
  targetB = b;
  currR = r;
  currG = g;
  currB = b;
  rgbLed.setPixelColor(0, rgbLed.Color(r, g, b));
  rgbLed.show();
}

void setPwmFreq(float hz) {
  SERVO_HZ = hz;
  pca.setPWMFreq(SERVO_HZ);
  delay(10);
}

// ========= WebSocket helpers =========
void sendOk(uint8_t clientNum) {
  txDoc.clear();
  txDoc["ok"] = true;
  String response;
  serializeJson(txDoc, response);
  webSocket.sendTXT(clientNum, response);
}

void sendError(uint8_t clientNum, const char *msg) {
  txDoc.clear();
  txDoc["ok"] = false;
  txDoc["err"] = msg;
  String response;
  serializeJson(txDoc, response);
  webSocket.sendTXT(clientNum, response);
}

void sendStatus(uint8_t clientNum) {
  txDoc.clear();
  txDoc["status"] = true;
  txDoc["moving"] = moving;
  JsonArray angles = txDoc["angles"].to<JsonArray>();
  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    angles.add(currDeg[i]);
  }
  txDoc["led"] = currLed;
  txDoc["rgb"]["r"] = currR;
  txDoc["rgb"]["g"] = currG;
  txDoc["rgb"]["b"] = currB;
  String response;
  serializeJson(txDoc, response);
  webSocket.sendTXT(clientNum, response);
}

void broadcastStatus() {
  txDoc.clear();
  txDoc["status"] = true;
  txDoc["moving"] = moving;
  JsonArray angles = txDoc["angles"].to<JsonArray>();
  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    angles.add(currDeg[i]);
  }
  txDoc["led"] = currLed;
  txDoc["rgb"]["r"] = currR;
  txDoc["rgb"]["g"] = currG;
  txDoc["rgb"]["b"] = currB;
  String response;
  serializeJson(txDoc, response);
  webSocket.broadcastTXT(response);
}

void handleJsonMessage(uint8_t clientNum, const char *payload) {
  rxDoc.clear();
  DeserializationError err = deserializeJson(rxDoc, payload);
  if (err) {
    sendError(clientNum, "bad_json");
    return;
  }

  const char *cmd = rxDoc["cmd"] | "";

  if (strcmp(cmd, "ping") == 0) {
    txDoc.clear();
    txDoc["pong"] = true;
    String response;
    serializeJson(txDoc, response);
    webSocket.sendTXT(clientNum, response);
    return;
  }

  if (strcmp(cmd, "home") == 0) {
    float d[NUM_SERVOS];
    for (uint8_t i = 0; i < NUM_SERVOS; i++) d[i] = 0.0f; // center (1.5 ms)
    uint32_t ms = rxDoc["ms"] | 800;
    uint8_t ledVal = rxDoc["led"] | currLed;
    uint8_t r = rxDoc["rgb"]["r"] | 0;
    uint8_t g = rxDoc["rgb"]["g"] | 0;
    uint8_t b = rxDoc["rgb"]["b"] | 0;
    startMove(d, ms, ledVal, r, g, b);
    sendOk(clientNum);
    return;
  }

  if (strcmp(cmd, "led") == 0) {
    int v = rxDoc["val"] | -1;
    if (v < 0 || v > 255) {
      sendError(clientNum, "led_range_0_255");
      return;
    }
    setLed((uint8_t)v);
    sendOk(clientNum);
    return;
  }

  if (strcmp(cmd, "rgb") == 0) {
    int r = rxDoc["r"] | -1;
    int g = rxDoc["g"] | -1;
    int b = rxDoc["b"] | -1;
    if (r < 0 || r > 255 || g < 0 || g > 255 || b < 0 || b > 255) {
      sendError(clientNum, "rgb_range_0_255");
      return;
    }
    setRgbLed((uint8_t)r, (uint8_t)g, (uint8_t)b);
    sendOk(clientNum);
    return;
  }

  if (strcmp(cmd, "freq") == 0) {
    // Keep 50 Hz for servos. Range check anyway.
    float hz = rxDoc["hz"] | 50.0f;
    if (hz < 40.0f || hz > 60.0f) {
      sendError(clientNum, "freq_out_of_range_40_60");
      return;
    }
    setPwmFreq(hz);
    sendOk(clientNum);
    return;
  }

  if (strcmp(cmd, "config") == 0) {
    int ch = rxDoc["ch"] | -1;
    if (ch < 0 || ch >= (int)NUM_SERVOS) {
      sendError(clientNum, "bad_ch");
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
    sendOk(clientNum);
    return;
  }

  if (strcmp(cmd, "frame") == 0) {
    // "deg" expects -90..+90 for each joint. Missing values = hold.
    JsonArray arr = rxDoc["deg"].as<JsonArray>();
    if (arr.isNull() || arr.size() == 0) {
      sendError(clientNum, "missing_deg");
      return;
    }
    float d[NUM_SERVOS];
    for (uint8_t i = 0; i < NUM_SERVOS; i++) {
      d[i] = (i < arr.size()) ? (float)arr[i].as<float>() : currDeg[i];
    }
    uint32_t ms = rxDoc["ms"] | 100;
    int ledVal = rxDoc["led"] | currLed;
    if (ledVal < 0) ledVal = currLed;
    
    uint8_t r = rxDoc["rgb"]["r"] | currR;
    uint8_t g = rxDoc["rgb"]["g"] | currG;
    uint8_t b = rxDoc["rgb"]["b"] | currB;
    
    startMove(d, ms, (uint8_t)ledVal, r, g, b);
    sendOk(clientNum);
    return;
  }

  if (strcmp(cmd, "status") == 0) {
    sendStatus(clientNum);
    return;
  }

  sendError(clientNum, "unknown_cmd");
}

void onWebSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.printf("Client[%u] disconnected\n", num);
      break;
      
    case WStype_CONNECTED: {
      IPAddress ip = webSocket.remoteIP(num);
      Serial.printf("Client[%u] connected from %d.%d.%d.%d\n", num, ip[0], ip[1], ip[2], ip[3]);
      
      // Send welcome message
      txDoc.clear();
      txDoc["ready"] = true;
      txDoc["servos"] = NUM_SERVOS;
      txDoc["wifi_ip"] = WiFi.softAPIP().toString();
      String welcome;
      serializeJson(txDoc, welcome);
      webSocket.sendTXT(num, welcome);
      break;
    }
    
    case WStype_TEXT:
      Serial.printf("Client[%u] sent: %s\n", num, payload);
      handleJsonMessage(num, (char*)payload);
      break;
      
    case WStype_BIN:
      Serial.printf("Client[%u] sent binary data (%u bytes)\n", num, length);
      break;
      
    default:
      break;
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(5);
  Serial.println("Starting ESP32 RoboArm with WiFi and WebSocket...");

  // Initialize I2C and PCA9685
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN, 400000); // 400 kHz
  pca.begin();
  setPwmFreq(SERVO_HZ); // 50 Hz

  // Initialize PWM LED
  ledcSetup(LEDC_CH, LEDC_FREQ, LEDC_RES);
  ledcAttachPin(LED_PIN, LEDC_CH);
  setLed(0);

  // Initialize RGB LED
  rgbLed.begin();
  rgbLed.setBrightness(50); // Not too bright
  setRgbLed(0, 0, 0); // Start with LED off

  // Initialize servos at center (0 deg -> 1.5 ms)
  applyAllOutputs();

  // Setup WiFi Access Point
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET);
  WiFi.softAP(AP_SSID, AP_PASS);
  
  Serial.println("WiFi AP started");
  Serial.print("AP SSID: ");
  Serial.println(AP_SSID);
  Serial.print("AP IP: ");
  Serial.println(WiFi.softAPIP());

  // Start WebSocket server
  webSocket.begin();
  webSocket.onEvent(onWebSocketEvent);
  Serial.print("WebSocket server started on port ");
  Serial.println(WS_PORT);

  // Welcome RGB animation
  setRgbLed(0, 255, 0); // Green = ready
  delay(500);
  setRgbLed(0, 0, 0); // Off
  
  Serial.println("Setup complete - ready for WebSocket connections");
}

void loop() {
  webSocket.loop();
  updateMotion();
}