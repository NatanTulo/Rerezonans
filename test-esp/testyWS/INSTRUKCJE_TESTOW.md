# Instrukcje testowania opóźnień ESP32 RoboArm

## Przygotowanie środowiska

### 1. Wgraj firmware do ESP32
```bash
cd /home/natan/Hackaton/rerenesans/roboarm
~/.platformio/penv/bin/platformio run --target upload
```

### 2. Sprawdź czy ESP32 działa
- Po resecie ESP32 powinien utworzyć sieć WiFi `ESP32_RoboArm`
- Sprawdź Serial Monitor: `~/.platformio/penv/bin/platformio device monitor`
- Powinieneś zobaczyć: "WiFi AP started" i "WebSocket server started"

## Połączenie z ESP32

### 1. Przełącz WiFi na hotspot ESP32
```bash
# Sprawdź dostępne sieci
sudo iwlist scan | grep ESP32_RoboArm

# Rozłącz obecne WiFi (opcjonalne)
sudo nmcli device disconnect wlan0

# Połącz z ESP32
sudo nmcli device wifi connect "ESP32_RoboArm" password "roboarm123"

# Sprawdź połączenie
ip route show
ping 192.168.4.1
```

### 2. Alternatywnie przez GUI
1. Kliknij na ikonę WiFi w systemie
2. Wybierz sieć `ESP32_RoboArm`
3. Wpisz hasło: `roboarm123`
4. Sprawdź czy masz IP z zakresu 192.168.4.x

## Testy wydajności

### Test 1: Podstawowy test łączności
```bash
cd /home/natan/Hackaton/rerenesans/test-esp
python3 test_proto.py
```
**Oczekiwany wynik:** Wszystkie polecenia powinny dostać odpowiedź `{"ok":true}` lub dane bez opóźnień.

### Test 2: Pomiar opóźnień
```bash
python3 latency_test.py
```
**Oczekiwane opóźnienia:**
- Round-trip ping: < 5ms
- Frame commands: < 10ms
- Dla płynnego ruchu: < 20ms

### Test 3: Test sterowania w czasie rzeczywistym
```bash
python3 realtime_control_test.py
```
**Sprawdź:**
- Czy wszystkie polecenia są wysyłane bez błędów
- Czy opóźnienia są stabilne
- Czy nie ma timeoutów

### Test 4: Test wydajności przy różnych częstotliwościach
```bash
# Test 10 Hz (100ms)
python3 latency_test.py --frequency 10

# Test 20 Hz (50ms) 
python3 latency_test.py --frequency 20

# Test 50 Hz (20ms)
python3 latency_test.py --frequency 50
```

## Interpretacja wyników

### ✅ DOBRE wyniki (nadaje się do sterowania w czasie rzeczywistym):
- **Ping:** < 5ms średnio
- **Frame:** < 10ms średnio
- **Stabilność:** < 90% poleceń w czasie < 20ms
- **Bez timeoutów** przy częstotliwości 20-50 Hz

### ⚠️ ŚREDNIE wyniki (ograniczone sterowanie):
- **Ping:** 5-15ms średnio
- **Frame:** 10-30ms średnio
- **Stabilność:** 70-90% poleceń w czasie < 50ms
- **Sporadyczne timeouty** przy > 20 Hz

### ❌ SŁABE wyniki (tylko pozycyjne sterowanie):
- **Ping:** > 15ms średnio
- **Frame:** > 30ms średnio
- **Stabilność:** < 70% w czasie
- **Częste timeouty** przy > 10 Hz

## Analiza problemów

### Problem: Wysokie opóźnienia (> 50ms)
**Możliwe przyczyny:**
- Słaby sygnał WiFi - zbliż się do ESP32
- Interferacja - sprawdź inne sieci 2.4GHz
- Przeciążenie ESP32 - zrestartuj urządzenie

### Problem: Timeouty
**Możliwe przyczyny:**
- Za wysoka częstotliwość wysyłania
- ESP32 nie nadąża z przetwarzaniem
- Problemy z WebSocket connection

### Problem: Niestabilne czasy
**Możliwe przyczyny:**
- Fragmentacja pamięci w ESP32
- Interferencia WiFi
- Problemy z zasilaniem ESP32

## Optymalizacja dla płynnego ruchu

### Strategia 1: Adaptive frequency
```python
# Dostosuj częstotliwość do opóźnień
if avg_latency < 10:
    frequency = 50  # 50 Hz
elif avg_latency < 20:
    frequency = 20  # 20 Hz
else:
    frequency = 10  # 10 Hz
```

### Strategia 2: Frame buffering
```python
# Wyślij kilka pozycji naraz
frames = [
    {"deg": [0, 10, 0, 0, 0], "ms": 20},
    {"deg": [0, 20, 0, 0, 0], "ms": 20},
    {"deg": [0, 30, 0, 0, 0], "ms": 20}
]
```

### Strategia 3: Interpolacja po stronie ESP32
- Wyślij pozycję docelową i czas
- ESP32 sam interpoluje ruch
- Mniej komunikacji = mniejsze opóźnienia

## Powrót do normalnego WiFi

```bash
# Rozłącz z ESP32
sudo nmcli device disconnect wlan0

# Połącz z normalnym WiFi
sudo nmcli device wifi connect "TWOJA_SIEC" password "TWOJE_HASLO"

# Sprawdź internet
ping google.com
```

## Przykładowe logi dobrych wyników

```
=== Test opóźnień WebSocket ===
Połączono z ws://192.168.4.1:81
Wiadomość powitalna w 2.34ms

Ping test (100 prób):
- Średni czas: 3.2ms
- Min: 1.1ms, Max: 8.7ms
- 95% < 5ms ✅

Frame test (50 prób):
- Średni czas: 5.8ms  
- Min: 2.3ms, Max: 12.1ms
- 90% < 10ms ✅

WYNIK: ESP32 nadaje się do sterowania w czasie rzeczywistym!
Rekomendowana częstotliwość: 30-40 Hz
```

## Co robić z wynikami

### Jeśli wyniki są DOBRE:
- Możesz implementować sterowanie w czasie rzeczywistym
- Użyj częstotliwości 20-50 Hz
- Implementuj adaptive control

### Jeśli wyniki są ŚREDNIE:
- Ograniczać częstotliwość do 10-20 Hz
- Użyj interpolacji po stronie ESP32
- Implementuj predykcję ruchu

### Jeśli wyniki są SŁABE:
- Użyj tylko sterowania pozycyjnego
- Wyślij całą trajektorię naraz
- Rozważ użycie przewodowego połączenia

## Pytania do przeanalizowania

1. **Jaki średni czas ping?**
2. **Jaki średni czas frame commands?**
3. **Przy jakiej częstotliwości zaczynają się timeouty?**
4. **Czy czasy są stabilne czy bardzo zmienne?**
5. **Czy sterowanie jest responsywne?**

Prześlij mi te wyniki, a pomogę zoptymalizować system! 🚀
