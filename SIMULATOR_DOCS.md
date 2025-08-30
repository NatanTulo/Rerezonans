# 🎨 Light Painting Simulator - Dokumentacja

## 📋 **OPIS**

**Light Painting Simulator** to kompletna aplikacja symulująca system light painting **bez potrzeby ESP32 i fizycznego robota**. Została stworzona na podstawie pracy zespołu z hackatonu, wykorzystując:

- ✅ **`ikpy_vis.py`** - wizualizacja 3D robota z animacją
- ✅ **`kontury.py`** - interaktywne rysowanie konturów na obrazie
- ✅ **`calcDegrees.py`** - kinematyka odwrotna PUMA
- ✅ **Nowe funkcje** - symulacja kropek light painting z długim naświetlaniem

## 🎯 **FUNKCJONALNOŚCI**

### **1. Przetwarzanie obrazu**
- 📁 Wczytywanie obrazów (PNG, JPG, BMP, TIFF)
- ✏️ Interaktywne rysowanie konturów (z `kontury.py`)
- 🔄 Automatyczne wykrywanie krawędzi (Canny)
- 🧮 Konwersja pikseli na współrzędne robota

### **2. Wizualizacja 3D robota**
- 🤖 Symulacja robota PUMA w 3D (z `ikpy_vis.py`)
- 🔴 Wizualizacja przegubów i segmentów
- 🟢 Końcówka z LED RGB w czasie rzeczywistym
- 📊 Animacja ruchu robota

### **3. Light Painting**
- 🎨 **Symulacja długiego naświetlania** - małe kolorowe kropki
- 🌈 Automatyczne kolory RGB na podstawie ścieżki
- ⏱️ Kontrola prędkości animacji
- 🖼️ Czarne tło symulujące prawdziwe light painting

### **4. Kinematyka**
- 🧮 Pełna kinematyka odwrotna (ikpy) lub uproszczona
- ⚙️ Parametry robota PUMA z istniejących plików
- 🎯 Automatyczne obliczanie kątów serw
- ✅ Weryfikacja osiągalności pozycji

## 🚀 **INSTRUKCJA UŻYCIA**

### **Krok 1: Uruchomienie**
```bash
cd /home/natan/Hackaton/Rerezonans
python light_painting_simulator.py
```

### **Krok 2: Wczytaj obraz**
1. Kliknij **"📁 Wczytaj obraz"**
2. Wybierz obraz (lub użyj `test_star.png`)
3. Status: "Obraz wczytany - możesz rysować kontury"

### **Krok 3: Rysuj kontury**
1. Kliknij **"✏️ Rysuj kontury"**
2. **Mysz** - rysuj kontury na obrazie
3. **BACKSPACE** - usuń ostatni kontur
4. **ENTER** - zatwierdź i zamknij

### **Krok 4: Ustaw parametry**
- **Skala**: 0.005 (jak duże mają być ruchy robota)
- **Offset X/Y**: 0.5 (pozycja środka obrazu)
- **Wysokość Z**: 1.5 (wysokość rysowania)
- **Prędkość**: 50 (szybkość animacji)

### **Krok 5: Uruchom symulację**
1. Kliknij **"🚀 Start Light Painting"**
2. Obserwuj robot w lewym oknie (3D)
3. Obserwuj kropki light painting w prawym oknie

### **Dodatkowe kontrole:**
- **⏸️ Stop** - zatrzymaj symulację
- **🗑️ Wyczyść** - reset do stanu początkowego

## 🖼️ **OKNA APLIKACJI**

### **Lewe okno: 🤖 Symulacja robota 3D**
- Niebiskie linie = segmenty robota
- Czerwone punkty = przeguby
- Zielony punkt = końcówka
- Kolorowa gwiazdka = LED RGB (zmienia kolor)

### **Prawe okno: 🎨 Light Painting**
- Czarne tło = symulacja długiego naświetlania
- Kolorowe kropki = ślady LED podczas ruchu
- Różne kolory = różne części ścieżki

## ⚙️ **PARAMETRY KONWERSJI**

| Parametr | Opis | Przykład | Efekt |
|----------|------|----------|-------|
| **Skala** | Ile metrów na piksel | 0.005 | Większa = większe ruchy |
| **Offset X** | Przesunięcie w osi X | 0.5 | Centrum robota |
| **Offset Y** | Przesunięcie w osi Y | 0.5 | Centrum robota |
| **Wysokość Z** | Wysokość rysowania | 1.5 | Bezpieczna wysokość |
| **Prędkość** | Szybkość animacji | 50 | Większa = szybciej |

## 🔧 **TROUBLESHOOTING**

### **Problem: "Brak trajektorii"**
**Rozwiązanie:**
1. Sprawdź czy narysowałeś kontury
2. Zmniejsz skalę (np. na 0.001)
3. Sprawdź offset Z (powinien być > 1.0)

### **Problem: "Wszystkie punkty niedostępne"**
**Rozwiązanie:**
1. Zwiększ offset Z (np. 2.0)
2. Zmniejsz skalę
3. Przesuń offset X/Y bliżej środka (0.5, 0.5)

### **Problem: Robot nie rusza się**
**Rozwiązanie:**
1. Sprawdź logi w dolnym oknie
2. Użyj przycisku "🗑️ Wyczyść" i spróbuj ponownie
3. Restart aplikacji

## 📊 **RÓŻNICE vs PRAWDZIWY SYSTEM**

| Funkcja | Symulator | Prawdziwy system |
|---------|-----------|------------------|
| **ESP32** | ❌ Nie potrzeba | ✅ Wymagany |
| **WebSocket** | ❌ Nie używa | ✅ Komunikacja |
| **Fizyczny robot** | ❌ Symulacja 3D | ✅ Prawdziwy PUMA |
| **LED RGB** | ✅ Symulacja kolorów | ✅ Prawdziwa dioda |
| **Light painting** | ✅ Kropki na ekranie | ✅ Prawdziwe światło |
| **Kinematyka** | ✅ Identyczna | ✅ Identyczna |
| **Przetwarzanie obrazu** | ✅ Identyczne | ✅ Identyczne |

## 💡 **ZALETY SYMULATORA**

### **Dla rozwoju:**
- 🚀 **Szybkie testowanie** - bez konfiguracji hardware
- 🔍 **Debugowanie** - pełna kontrola nad procesem
- 🎨 **Wizualizacja** - widzisz co się dzieje w 3D
- 💾 **Zapisywanie** - możliwość analizy rezultatów

### **Dla prezentacji:**
- 📱 **Demo bez hardware** - zawsze działa
- 🎥 **Capture-friendly** - łatwe nagrywanie
- 🎨 **Ładne wizualizacje** - imponuje publiczności
- ⚡ **Szybkie** - nie czeka na prawdziwy robot

### **Dla zespołu:**
- 👥 **Wszyscy mogą testować** - bez dostępu do robota
- 🏠 **Praca zdalna** - nie potrzeba być na miejscu
- 🔧 **Bezpieczne** - nie ma ryzyka uszkodzenia
- 📚 **Edukacyjne** - pokazuje kinematykę w akcji

## 🎉 **PODSUMOWANIE**

**Light Painting Simulator** to kompletne rozwiązanie backup dla projektu REREZONANS. Wykorzystuje całą pracę zespołu z hackatonu i pozwala na:

1. **Pełną demonstrację** systemu bez ESP32
2. **Testowanie algorytmów** przetwarzania obrazu
3. **Wizualizację kinematyki** robota w 3D
4. **Symulację light painting** z kolorowymi kropkami

**Idealne jako:**
- 🎯 **Backup** gdyby hardware nie działał
- 🧪 **Środowisko testowe** dla nowych funkcji
- 🎪 **Demo** na prezentacji/konkursie
- 📚 **Narzędzie edukacyjne** do nauki robotyki

**Aplikacja gotowa do użycia!** 🚀
