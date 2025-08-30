# 🎨 Light Painting Robot - PUMA Arm Project

**Zespół hackaton: Rerezonans** | **Data: 2025-08-31**

Projekt ramienia robotycznego PUMA z funkcją light painting - tworzenia obrazów światłem w długim naświetlaniu. System składa się z ESP32 jako kontrolera sprzętowego oraz zaawansowanych aplikacji Python do planowania ruchu i symulacji.

## 🚀 Funkcje systemu

### 🤖 **Główne aplikacje Python**
- **Light Painting Simulator** - Autonomiczny symulator z wizualizacją 3D
- **Integrated App** - Pełna aplikacja z komunikacją ESP32 + symulacja
- **Kinematyka odwrotna** - PUMA robot z biblioteką ikpy
- **Interaktywne rysowanie** - OpenCV do tworzenia konturów
- **Wizualizacja 3D** - Matplotlib do animacji robota

### ⚡ **ESP32 Hardware Controller**
- WiFi hotspot: `ESP32_RoboArm` (hasło: `roboarm123`)
- WebSocket serwer na porcie 81
- Kontrola 5 serwosilników (PUMA kinematics)
- Dioda RGB adresowalna (NeoPixel) dla light painting
- Komunikacja JSON przez WebSocket

## 📁 Struktura projektu

```
├── light_painting_simulator.py  # 🎨 SYMULATOR - działa bez ESP32
├── integrated_app.py           # 🔧 GŁÓWNA APLIKACJA z ESP32
├── requirements.txt            # 📦 Wszystkie zależności Python
├── roboarm/                    # 🔌 Kod ESP32 (PlatformIO)
│   ├── platformio.ini
│   └── src/main.cpp
├── test-esp/                   # 🧪 Narzędzia testowe
│   ├── gui_proto.py           # WebSocket test client
│   └── testyWS/               # Zaawansowane testy
└── archive/                    # 📚 Oryginalne pliki zespołu
    ├── ikpy_vis.py            # Wizualizacja 3D
    ├── kontury.py             # Interaktywne rysowanie
    └── calcDegrees.py         # Kinematyka robota
```

## 🔧 Instalacja i uruchomienie

### **Krok 1: Przygotowanie środowiska Python**
```bash
# Klonowanie repozytorium
git clone https://github.com/NatanTulo/Rerezonans.git
cd Rerezonans

# Utworzenie środowiska wirtualnego
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# lub: venv\Scripts\activate  # Windows

# Instalacja zależności
pip install -r requirements.txt
```

### **Krok 2A: Uruchomienie symulatora (bez ESP32)**
```bash
python light_painting_simulator.py
```
**Funkcje symulatora:**
- ✅ Pełna wizualizacja 3D robota PUMA
- ✅ Interaktywne rysowanie konturów
- ✅ Symulacja light painting
- ✅ Kinematyka odwrotna z ikpy
- ✅ Działa autonomicznie

### **Krok 2B: Uruchomienie głównej aplikacji (z ESP32)**
```bash
python integrated_app.py
```
**Wymagania:**
- ESP32 zaprogramowany (instrukcje poniżej)
- Połączenie WiFi z ESP32_RoboArm

## 🤖 Programowanie ESP32

### **Instalacja PlatformIO**
```bash
# Instalacja PlatformIO CLI
curl -fsSL https://raw.githubusercontent.com/platformio/platformio-core-installer/master/get-platformio.py -o get-platformio.py
python3 get-platformio.py

# Lub przez VSCode extension: PlatformIO IDE
```

### **Wgranie firmware**
```bash
cd roboarm
~/.platformio/penv/bin/platformio run --target upload
```

### **Hardware - podłączenia:**
- **I2C (PCA9685)**: SDA=21, SCL=22
- **LED RGB**: Pin 17 (NeoPixel WS2812)
- **Serwa PUMA**: Kanały 0-4 na PCA9685
  - Kanały 0-2: MG996R (większe serwa)
  - Kanały 3-4: MG90S (mniejsze serwa)

## 📡 Komunikacja ESP32 - Protokoły WebSocket

### **Połączenie z ESP32**
1. Połącz się z WiFi: `ESP32_RoboArm`, hasło: `roboarm123`
2. IP ESP32: `192.168.4.1`
3. WebSocket: `ws://192.168.4.1:81`

### **Protokół komunikacji JSON**

#### ✅ **Ping** (test połączenia)
```json
{"cmd": "ping"}
```
**Odpowiedź:** `{"pong": true}`

#### 🏠 **Home position** (pozycja wyjściowa)
```json
{
  "cmd": "home",
  "ms": 800,
  "led": 128,
  "rgb": {"r": 0, "g": 255, "b": 0}
}
```

#### 🤖 **Ruch serw** (główne polecenie ruchu)
```json
{
  "cmd": "frame",
  "deg": [10, -20, 15, -5, 30],
  "ms": 1000,
  "led": 200,
  "rgb": {"r": 0, "g": 0, "b": 255}
}
```
- `deg`: kąty [-90°, 90°] dla 5 serw PUMA
- `ms`: czas ruchu w milisekundach
- `rgb`: kolor LED podczas ruchu

#### 💡 **Kontrola LED RGB**
```json
{"cmd": "rgb", "r": 255, "g": 0, "b": 0}
```

#### 📊 **Status robota**
```json
{"cmd": "status"}
```
**Odpowiedź:** aktualny stan serw i LED

### **Test komunikacji**
```bash
cd test-esp
python gui_proto.py  # GUI test client
# lub
python test_proto.py --host 192.168.4.1 --port 81
```

## 🎨 Jak używać systemu Light Painting

### **1. Symulator (bez sprzętu)**
1. Uruchom `python light_painting_simulator.py`
2. Kliknij "📁 Wczytaj obraz"
3. Kliknij "✏️ Rysuj kontury" - narysuj interaktywnie lub użyj auto-detect
4. Kliknij "🚀 Start Light Painting"
5. Obserwuj symulację 3D + light painting canvas

### **2. Pełny system (z ESP32)**
1. Zaprogramuj ESP32 i podłącz serwa
2. Uruchom `python integrated_app.py`
3. Zakładka "WebSocket": połącz z ESP32
4. Zakładka "Light Painting": wczytaj obraz i rysuj kontury  
5. Zakładka "Robot Control": uruchom sekwencję light painting

## 🔬 Zaawansowane funkcje

### **Testowanie komunikacji WebSocket**
```bash
cd test-esp/testyWS
python quick_test_all_modes.py      # Szybki test wszystkich funkcji
python advanced_control_test.py     # Zaawansowana kontrola
python latency_test.py              # Test opóźnień
python realtime_control_test.py     # Kontrola w czasie rzeczywistym
```

### **Konfiguracja kinematyki**
W `light_painting_simulator.py` i `integrated_app.py` można dostroić:
- Parametry DH robota PUMA
- Skalę konwersji obraz → współrzędne robota
- Prędkość ruchu i interpolację kolorów

## 👥 Zespół i architektura

**Projekt bazuje na pracy zespołu hackathonu:**
- `ikpy_vis.py` → Wizualizacja 3D robota (w `light_painting_simulator.py`)
- `kontury.py` → Interaktywne rysowanie konturów  
- `calcDegrees.py` → Kinematyka odwrotna PUMA

**Nowa architektura:**
- **Symulator** - wszystko w jednym, bez ESP32
- **Integrated App** - łączy symulację z rzeczywistym ESP32
- **Modularna struktura** - każda funkcja w osobnych klasach

## 📚 Dokumentacja techniczna

- **SIMULATOR_DOCS.md** - Szczegółowa dokumentacja symulatora
- **ZAAWANSOWANE_TRYBY.md** - Tryby zaawansowane i konfiguracja
- **PERFORMANCE_ANALYSIS.md** - Analiza wydajności systemu

## 🚨 Rozwiązywanie problemów

### **Błąd OpenCV GUI**
Symulator ma automatyczny fallback - jeśli interaktywne rysowanie nie działa, używa automatycznego wykrywania konturów.

### **Błąd połączenia ESP32**
1. Sprawdź połączenie WiFi z `ESP32_RoboArm`
2. Zweryfikuj IP: `192.168.4.1`
3. Użyj test clienta: `python test-esp/gui_proto.py`

### **Błąd ikpy**
Aplikacje działają również bez ikpy (uproszczona kinematyka). Zalecana instalacja: `pip install ikpy`

---

**🎉 Gotowy do Light Painting! Ciesz się tworzeniem sztuki światłem! ✨**
