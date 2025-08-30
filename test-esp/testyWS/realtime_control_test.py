#!/usr/bin/env python3
"""
Test sterowania w czasie rzeczywistym - symuluje płynny ruch robota.
Sprawdza czy można uzyskać kontrolę o wysokiej częstotliwości.
"""

import asyncio
import json
import time
import math
import websockets

class RealTimeController:
    def __init__(self, host="192.168.4.1", port=81):
        self.host = host
        self.port = port
        self.websocket = None
        self.connected = False
        
    async def connect(self):
        try:
            uri = f"ws://{self.host}:{self.port}"
            self.websocket = await websockets.connect(uri)
            welcome = await self.websocket.recv()
            print(f"🔗 Połączono: {json.loads(welcome)}")
            self.connected = True
            return True
        except Exception as e:
            print(f"❌ Błąd połączenia: {e}")
            return False
    
    async def send_frame_fast(self, angles, duration_ms=100):
        """Wysyła frame command bez czekania na odpowiedź (fire-and-forget)."""
        if not self.connected:
            return False
            
        cmd = {
            "cmd": "frame", 
            "deg": angles, 
            "ms": duration_ms
        }
        
        try:
            await self.websocket.send(json.dumps(cmd))
            return True
        except:
            return False
    
    async def send_frame_safe(self, angles, duration_ms=200):
        """Wysyła frame command i czeka na potwierdzenie."""
        if not self.connected:
            return False, -1
            
        cmd = {
            "cmd": "frame",
            "deg": angles,
            "ms": duration_ms
        }
        
        try:
            start = time.perf_counter()
            await self.websocket.send(json.dumps(cmd))
            response = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
            latency = (time.perf_counter() - start) * 1000
            return True, latency
        except:
            return False, -1

    def generate_smooth_trajectory(self, duration_sec=10, frequency_hz=20):
        """Generuje płynną trajektorię dla wszystkich 5 serw."""
        total_points = int(duration_sec * frequency_hz)
        trajectory = []
        
        for i in range(total_points):
            t = i / (total_points - 1)  # 0 to 1
            
            # Różne wzorce ruchu dla każdego serwa
            angles = [
                20 * math.sin(2 * math.pi * t),           # Servo 0: sinus
                15 * math.cos(2 * math.pi * t * 1.5),     # Servo 1: cosinus 1.5x szybszy
                10 * math.sin(2 * math.pi * t * 0.7),     # Servo 2: sinus wolniejszy
                25 * math.sin(2 * math.pi * t * 2),       # Servo 3: sinus 2x szybszy
                30 * math.cos(2 * math.pi * t * 0.3)      # Servo 4: bardzo wolny cosinus
            ]
            
            # Zaokrągl do 1 miejsca po przecinku
            angles = [round(a, 1) for a in angles]
            trajectory.append(angles)
        
        return trajectory

    async def test_fire_and_forget(self, frequency_hz=20, duration_sec=10):
        """Test sterowania fire-and-forget (bez czekania na odpowiedź)."""
        print(f"\n🚀 Test FIRE-AND-FORGET ({frequency_hz} Hz, {duration_sec}s)")
        print("-" * 50)
        
        trajectory = self.generate_smooth_trajectory(duration_sec, frequency_hz)
        interval = 1.0 / frequency_hz
        frame_duration_ms = int(interval * 1000 * 1.2)  # 20% dłużej niż interval
        
        print(f"📍 Punktów trajektorii: {len(trajectory)}")
        print(f"⏱️  Interwał: {interval*1000:.1f}ms")
        print(f"🎯 Czas ruchu frame: {frame_duration_ms}ms")
        
        sent_count = 0
        failed_count = 0
        start_time = time.perf_counter()
        
        for i, angles in enumerate(trajectory):
            loop_start = time.perf_counter()
            
            # Wyślij polecenie
            success = await self.send_frame_fast(angles, frame_duration_ms)
            if success:
                sent_count += 1
            else:
                failed_count += 1
            
            # Pokazuj postęp co sekundę
            if (i + 1) % frequency_hz == 0:
                elapsed = time.perf_counter() - start_time
                print(f"  {elapsed:.1f}s: wysłano {sent_count}, błędów {failed_count}")
            
            # Czekaj do następnej iteracji
            elapsed = time.perf_counter() - loop_start
            sleep_time = max(0, interval - elapsed)
            
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        total_time = time.perf_counter() - start_time
        actual_freq = sent_count / total_time
        
        print(f"\n📊 WYNIKI:")
        print(f"   Czas rzeczywisty: {total_time:.1f}s")
        print(f"   Wysłane polecenia: {sent_count}")
        print(f"   Błędy: {failed_count}")
        print(f"   Rzeczywista częstotliwość: {actual_freq:.1f} Hz")
        print(f"   Sprawność: {100*sent_count/(sent_count+failed_count):.1f}%")
        
        return actual_freq, sent_count, failed_count

    async def test_confirmed_mode(self, frequency_hz=10, duration_sec=5):
        """Test sterowania z potwierdzeniem (bezpieczny tryb)."""
        print(f"\n✅ Test CONFIRMED MODE ({frequency_hz} Hz, {duration_sec}s)")
        print("-" * 50)
        
        trajectory = self.generate_smooth_trajectory(duration_sec, frequency_hz)
        interval = 1.0 / frequency_hz
        frame_duration_ms = int(interval * 1000 * 1.5)
        
        latencies = []
        sent_count = 0
        failed_count = 0
        start_time = time.perf_counter()
        
        for i, angles in enumerate(trajectory):
            success, latency = await self.send_frame_safe(angles, frame_duration_ms)
            
            if success:
                sent_count += 1
                latencies.append(latency)
            else:
                failed_count += 1
            
            # Pokazuj postęp
            if (i + 1) % frequency_hz == 0:
                elapsed = time.perf_counter() - start_time
                avg_lat = sum(latencies[-frequency_hz:]) / min(frequency_hz, len(latencies)) if latencies else 0
                print(f"  {elapsed:.1f}s: wysłano {sent_count}, śr. latencja {avg_lat:.1f}ms")
            
            # Krótka pauza
            await asyncio.sleep(0.01)
        
        total_time = time.perf_counter() - start_time
        actual_freq = sent_count / total_time
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        print(f"\n📊 WYNIKI:")
        print(f"   Czas rzeczywisty: {total_time:.1f}s")
        print(f"   Wysłane polecenia: {sent_count}")
        print(f"   Błędy: {failed_count}")
        print(f"   Rzeczywista częstotliwość: {actual_freq:.1f} Hz")
        print(f"   Średnia latencja: {avg_latency:.1f}ms")
        print(f"   Sprawność: {100*sent_count/(sent_count+failed_count):.1f}%")
        
        return actual_freq, avg_latency, sent_count, failed_count

    async def close(self):
        if self.websocket:
            await self.websocket.close()


async def main():
    print("🤖 ESP32 Real-Time Control Test")
    print("=" * 50)
    
    controller = RealTimeController()
    
    # Spróbuj połączyć się z ESP32
    if not await controller.connect():
        print("\n❌ Nie można połączyć się z ESP32.")
        print("   Sprawdź czy:")
        print("   • ESP32 jest włączony")
        print("   • Jesteś połączony z siecią ESP32_RoboArm")
        print("   • IP 192.168.4.1 jest dostępne")
        print("\n🔧 Uruchamiam symulację offline...")
        
        # Symulacja offline
        await simulate_performance()
        return
    
    try:
        # Test 1: Fire-and-forget mode (wysokie częstotliwości)
        freq1, sent1, failed1 = await controller.test_fire_and_forget(
            frequency_hz=30, duration_sec=8
        )
        
        await asyncio.sleep(2)  # Pauza między testami
        
        # Test 2: Confirmed mode (bezpieczny)
        freq2, latency2, sent2, failed2 = await controller.test_confirmed_mode(
            frequency_hz=15, duration_sec=5
        )
        
        # Podsumowanie
        print("\n" + "=" * 50)
        print("🎯 PODSUMOWANIE TESTÓW:")
        print(f"🚀 Fire-and-forget: {freq1:.1f} Hz (sprawność: {100*sent1/(sent1+failed1):.1f}%)")
        print(f"✅ Confirmed mode: {freq2:.1f} Hz (latencja: {latency2:.1f}ms)")
        
        print("\n💡 REKOMENDACJE:")
        if freq1 > 25 and latency2 < 50:
            print("   ✅ DOSKONAŁY - sterowanie real-time możliwe!")
            print("   📈 Zalecane ustawienia:")
            print("      • Fire-and-forget: 20-30 Hz")
            print("      • Confirmed: 10-15 Hz") 
            print("      • Frame duration: 50-100ms")
        elif freq1 > 15 and latency2 < 100:
            print("   ✅ DOBRY - sterowanie płynne możliwe")
            print("   📈 Zalecane ustawienia:")
            print("      • Fire-and-forget: 15-20 Hz")
            print("      • Confirmed: 5-10 Hz")
            print("      • Frame duration: 100-200ms")
        else:
            print("   ⚠️  OGRANICZONY - tylko sterowanie sekwencyjne")
            print("   📈 Zalecane ustawienia:")
            print("      • Frequency: < 10 Hz")
            print("      • Frame duration: > 200ms")
        
    finally:
        await controller.close()


async def simulate_performance():
    """Symulacja wydajności gdy ESP32 nie jest dostępne."""
    print("\n🧮 SYMULACJA WYDAJNOŚCI")
    print("-" * 30)
    
    # Symulacja różnych latencji
    scenarios = [
        ("Doskonały WiFi", 10, 100),
        ("Dobry WiFi", 25, 80), 
        ("Średni WiFi", 50, 60),
        ("Słaby WiFi", 100, 40)
    ]
    
    for name, latency_ms, max_freq in scenarios:
        print(f"\n📡 {name} (latencja: {latency_ms}ms):")
        print(f"   Maksymalna częstotliwość: {max_freq} Hz")
        print(f"   Sterowanie real-time: {'✅ TAK' if latency_ms < 50 and max_freq > 20 else '❌ NIE'}")
        print(f"   Sterowanie płynne: {'✅ TAK' if latency_ms < 100 and max_freq > 10 else '❌ NIE'}")
    
    print(f"\n🎯 WNIOSEK:")
    print(f"   ESP32 WebSocket może obsłużyć sterowanie real-time")
    print(f"   przy dobrej jakości WiFi (< 30ms latencji)")


if __name__ == "__main__":
    asyncio.run(main())
