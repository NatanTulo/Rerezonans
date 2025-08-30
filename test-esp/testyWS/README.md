# 🧪 Testy WebSocket ESP32 RoboArm

Zorganizowane testy wydajności i funkcjonalności komunikacji WebSocket z ESP32.

## 📋 Dostępne testy

### 1. **`latency_test.py`** - Test podstawowej latencji
```bash
python3 latency_test.py
```
**Co testuje:**
- Ping latencja (100 prób)
- Frame command latencja (50 prób) 
- Testy częstotliwości: 10Hz, 20Hz, 30Hz, 50Hz
- Statystyki: średnia, mediana, min/max, odchylenie standardowe

**Rezultat:** Ocena czy system nadaje się do sterowania real-time

---

### 2. **`realtime_control_test.py`** - Test sterowania w czasie rzeczywistym
```bash
python3 realtime_control_test.py
```
**Co testuje:**
- Fire-and-forget mode (30Hz przez 8s)
- Confirmed mode (15Hz przez 5s)
- Płynne trajektorie ruchu dla wszystkich 5 serw
- Rzeczywistą częstotliwość vs zadaną

**Rezultat:** Sprawdzenie czy można osiągnąć płynny ruch robota

---

### 3. **`advanced_control_test.py`** - Test zaawansowanych trybów
```bash
python3 advanced_control_test.py
```
**Co testuje:**
- **RT_FRAME:** Real-time control (25Hz przez 5s)
- **TRAJECTORY:** Buforowanie sekwencji (4 punkty z RGB)
- **STREAM:** Tryb strumieniowy (30Hz przez 3s, ruch w ósemce)

**Rezultat:** Sprawdzenie wszystkich nowych trybów sterowania

---

### 4. **`quick_test_all_modes.py`** - Szybki test funkcjonalności
```bash
python3 quick_test_all_modes.py
```
**Co testuje:**
- FRAME: standardowy tryb
- RT_FRAME: 10 szybkich ruchów  
- TRAJECTORY: kolorowa sekwencja 4 punktów
- STREAM: ruch w ósemce przez 3s
- HOME: powrót do pozycji zerowej

**Rezultat:** Szybka weryfikacja że wszystkie tryby działają

---

## 🚀 Kolejność testowania

### Pierwszego uruchomienia:
1. **`quick_test_all_modes.py`** - sprawdź podstawową funkcjonalność
2. **`latency_test.py`** - zmierz wydajność sieci
3. **`realtime_control_test.py`** - sprawdź sterowanie real-time
4. **`advanced_control_test.py`** - przetestuj zaawansowane funkcje

### Podczas rozwoju:
- **`latency_test.py`** - po każdej zmianie w kodzie ESP32
- **`quick_test_all_modes.py`** - szybka weryfikacja funkcjonalności

## 📊 Interpretacja wyników

### Latencja ping:
- **< 5ms:** ✅ Doskonała
- **5-20ms:** ✅ Dobra  
- **20-50ms:** ⚠️ Średnia
- **> 50ms:** ❌ Słaba

### Częstotliwość real-time:
- **> 25Hz:** ✅ Doskonała (płynny ruch)
- **15-25Hz:** ✅ Dobra (akceptowalny ruch)
- **10-15Hz:** ⚠️ Średnia (dyskretny ruch)
- **< 10Hz:** ❌ Słaba (tylko sekwencje)

### Sprawność:
- **> 95%:** ✅ Doskonała
- **90-95%:** ✅ Dobra
- **80-90%:** ⚠️ Średnia  
- **< 80%:** ❌ Słaba

## 🔧 Wymagania

Upewnij się, że:
- ESP32 jest nagrany z najnowszym firmware
- Jesteś połączony z siecią WiFi `ESP32_RoboArm`
- ESP32 odpowiada na `192.168.4.1:81`
- Zainstalowane pakiety: `websockets`, `asyncio`

## 📝 Dokumentacja

- **`INSTRUKCJE_TESTOW.md`** - Szczegółowe instrukcje testowania
- **`../ZAAWANSOWANE_TRYBY.md`** - Dokumentacja wszystkich trybów sterowania
- **`../PERFORMANCE_ANALYSIS.md`** - Analiza wydajności i wyniki

---
**💡 Tip:** Uruchom `quick_test_all_modes.py` dla szybkiej demonstracji wszystkich możliwości systemu!
