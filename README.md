# ESP32 RoboArm - WebSocket Version

Projekt ramienia robotycznego ESP32 z obsługą WiFi hotspot i WebSocket.

## Funkcje

- **ESP32 jako hotspot WiFi** - sieć `ESP32_RoboArm` (hasło: `roboarm123`)
- **Serwer WebSocket** na porcie 81
- **Kontrola 5 serwosilników** przez PCA9685 (I2C)
- **Dioda PWM** przez pin 16 (poprzednia dioda, nadal używana)
- **Dioda RGB adresowalna** (NeoPixel) na pin 17
- **Komunikacja JSON** przez WebSocket

## Hardware

### Podłączenia:
- **I2C (PCA9685)**: SDA=21, SCL=22
- **Dioda PWM**: Pin 16 (sterowana przez LEDC)
- **Dioda RGB**: Pin 17 (NeoPixel WS2812)
- **Serwa**: Kanały 0-4 na PCA9685

### Serwa:
- Kanały 0-2: MG996R (większe serwa)
- Kanały 3-4: MG90S (mniejsze serwa)
- Zakres: -90° do +90°
- Częstotliwość PWM: 50Hz

## Programowanie ESP32

```bash
cd roboarm
~/.platformio/penv/bin/platformio run --target upload
```

## Komunikacja

### Połączenie WiFi
1. Połącz się z siecią WiFi: `ESP32_RoboArm`
2. Hasło: `roboarm123`
3. IP ESP32: `192.168.4.1`
4. WebSocket: `ws://192.168.4.1:81`

### Polecenia JSON

#### Ping
```json
{"cmd": "ping"}
```
Odpowiedź: `{"pong": true}`

#### Home position
```json
{
  "cmd": "home",
  "ms": 800,
  "led": 128,
  "rgb": {"r": 0, "g": 255, "b": 0}
}
```

#### Kontrola LED PWM
```json
{"cmd": "led", "val": 128}
```
- `val`: 0-255

#### Kontrola LED RGB
```json
{"cmd": "rgb", "r": 255, "g": 0, "b": 0}
```
- `r`, `g`, `b`: 0-255

#### Ruch serw
```json
{
  "cmd": "frame",
  "deg": [10, -20, 15, -5, 30],
  "ms": 1000,
  "led": 200,
  "rgb": {"r": 0, "g": 0, "b": 255}
}
```
- `deg`: tablica kątów [-90, 90] dla każdego serwa
- `ms`: czas ruchu w milisekundach
- `led`: jasność LED PWM (opcjonalne)
- `rgb`: kolor LED RGB (opcjonalne)

#### Status
```json
{"cmd": "status"}
```
Odpowiedź zawiera aktualny stan wszystkich serw i LED.

#### Konfiguracja serw
```json
{
  "cmd": "config",
  "ch": 0,
  "min_us": 1000,
  "max_us": 2000,
  "offset_us": 0,
  "invert": false
}
```

## Test Client

### Instalacja
```bash
cd test-esp
python3 -m venv venv
source venv/bin/activate
pip install websockets
```

### Uruchomienie
```bash
# Test bez połączenia
python test_proto.py --dry

# Połączenie z ESP32
python test_proto.py --host 192.168.4.1 --port 81
```

### Przykładowe polecenia w kliencie:
- Ping
- Home position z zielonym LED RGB
- Kontrola LED PWM i RGB
- Ruch serw z interpolacją kolorów
- Zapytanie o status

## Protokół WebSocket

1. **Połączenie**: Klient łączy się z `ws://192.168.4.1:81`
2. **Powitanie**: ESP32 wysyła JSON z informacjami o gotowości
3. **Polecenia**: Klient wysyła JSON, ESP32 odpowiada
4. **Status**: ESP32 wysyła okresowo status (co sekundę) jeśli są połączeni klienci

## Zmiany względem wersji Serial

- ✅ WiFi hotspot zamiast Serial
- ✅ WebSocket zamiast Serial JSON
- ✅ Dodano LED RGB adresowalne (NeoPixel)
- ✅ Zachowano LED PWM na pin 16
- ✅ Nowe polecenia: `rgb`, rozszerzone `home` i `frame`
- ✅ Okresowe wysyłanie statusu
- ✅ Interpolacja RGB podczas ruchu
