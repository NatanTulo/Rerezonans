# 🚀 Zaawansowane tryby sterowania ESP32 RoboArm

## Dostępne tryby

### 1. **FRAME** (standardowy)
```json
{"cmd": "frame", "deg": [10,-20,15,-5,30], "ms": 200}
```
- ✅ Zwraca potwierdzenie
- ⏱️ Średnia latencja
- 🔒 Bezpieczny

**Zastosowanie:** Normalne sterowanie z potwierdzeniem

---

### 2. **RT_FRAME** (real-time) 🚀
```json
{"cmd": "rt_frame", "deg": [10,-20,15,-5,30], "ms": 50}
```
- 🚀 **Fire-and-forget** (bez odpowiedzi)
- ⚡ **Minimalna latencja** (~0.3ms)
- 🎯 **Wysoka częstotliwość** (20-50Hz)

**Zastosowanie:** Sterowanie w czasie rzeczywistym, joystick, mocap

**Zalecenia:**
- `ms`: 40-100ms dla płynnego ruchu
- Częstotliwość: 20-30Hz
- Brak potwierdzenia = maksymalna prędkość

---

### 3. **TRAJECTORY** (buforowanie) 📋
```json
{
  "cmd": "trajectory", 
  "points": [
    {"deg": [0,0,0,0,0], "ms": 200, "rgb": {"r": 255, "g": 0, "b": 0}},
    {"deg": [10,-20,15,-5,30], "ms": 300, "rgb": {"r": 0, "g": 255, "b": 0}},
    {"deg": [0,0,0,0,0], "ms": 200, "rgb": {"r": 0, "g": 0, "b": 255}}
  ]
}
```
- 🗃️ **Buforowanie** na ESP32 (do 20 punktów)
- 🌐 **Odporność** na opóźnienia sieci
- ✨ **Kolorowe** akcenty RGB
- 🔄 **Automatyczne** wykonanie sekwencji

**Zastosowanie:** Złożone sekwencje, pokazy, animacje

**Zalecenia:**
- Maksymalnie 20 punktów
- Każdy punkt może mieć własny kolor RGB
- Idealny do programowania sekwencji offline

---

### 4. **STREAM** (strumieniowy) 🌊
```json
{"cmd": "stream_start", "freq": 50}
```
Następnie wysyłaj same pozycje:
```json
[10,-20,15,-5,30]
[11,-19,14,-4,29]
[12,-18,13,-3,28]
...
```
Zatrzymanie:
```json
{"cmd": "stream_stop"}
```

- 🌊 **Ciągły strumień** pozycji
- 🎛️ **Konfigurowalna częstotliwość** (1-100Hz)
- 📦 **Kompaktowe dane** (tylko array)
- ⚡ **Throttling** po stronie ESP32

**Zastosowanie:** Odtwarzanie nagrań, live streaming, sensor fusion

**Zalecenia:**
- Częstotliwość: 20-50Hz
- Wysyłaj same arrays, nie obiekty JSON
- ESP32 automatycznie kontroluje częstotliwość

---

## Porównanie wydajności

| Tryb | Latencja | Częstotliwość | Bezpieczeństwo | Zastosowanie |
|------|----------|---------------|----------------|--------------|
| **frame** | ~7ms | 10-15Hz | ✅ Wysokie | Normalne sterowanie |
| **rt_frame** | ~0.3ms | 25-50Hz | ⚠️ Średnie | Real-time control |
| **trajectory** | N/A | Sekwencyjny | ✅ Wysokie | Animacje, pokazy |
| **stream** | ~0.4ms | 20-50Hz | ⚠️ Średnie | Live streaming |

## Przykłady użycia

### Real-time kontrola (joystick)
```python
while joystick_active:
    x, y = read_joystick()
    angles = [x*30, y*20, 0, 0, 0]
    cmd = {"cmd": "rt_frame", "deg": angles, "ms": 40}
    await websocket.send(json.dumps(cmd))
    await asyncio.sleep(1/25)  # 25 Hz
```

### Zaprogramowana sekwencja
```python
sequence = [
    {"deg": [0,0,0,0,0], "ms": 500, "rgb": {"r": 255, "g": 0, "b": 0}},
    {"deg": [45,-30,20,0,0], "ms": 800, "rgb": {"r": 0, "g": 255, "b": 0}},
    {"deg": [0,0,0,0,0], "ms": 500, "rgb": {"r": 0, "g": 0, "b": 255}}
]
cmd = {"cmd": "trajectory", "points": sequence}
await websocket.send(json.dumps(cmd))
```

### Streaming pozycji
```python
await websocket.send('{"cmd": "stream_start", "freq": 30}')
for angles in recorded_positions:
    await websocket.send(json.dumps(angles))
    await asyncio.sleep(1/30)
await websocket.send('{"cmd": "stream_stop"}')
```

## Status i monitoring

Polecenie `status` zwraca informacje o wszystkich trybach:
```json
{
  "status": true,
  "moving": false,
  "angles": [0, 0, 0, 0, 0],
  "led": 0,
  "rgb": {"r": 0, "g": 0, "b": 0},
  "trajectory_mode": false,
  "trajectory_points": 0,
  "trajectory_index": 0,
  "stream_mode": false,
  "stream_freq": 30
}
```

## Rekomendacje

### Dla sterowania real-time:
- Użyj `rt_frame` z częstotliwością 20-30Hz
- Czas ruchu `ms`: 40-80ms
- Brak sprawdzania odpowiedzi

### Dla animacji i pokazów:
- Użyj `trajectory` z buforowaniem
- Dodaj efekty RGB dla każdego punktu
- Maksymalnie 20 punktów na raz

### Dla odtwarzania nagrań:
- Użyj `stream` mode z odpowiednią częstotliwością
- Wysyłaj kompaktowe dane (arrays)
- ESP32 automatycznie kontroluje timing

---
**💡 Tip:** Wszystkie tryby można mieszać - np. `trajectory` do głównej animacji i `rt_frame` do korekcji w czasie rzeczywistym!
