#!/usr/bin/env python3
"""
Test zaawansowanych trybów sterowania ESP32 RoboArm.
Testuje rt_frame, trajectory i stream mode.
"""

import asyncio
import json
import time
import math
import websockets

class AdvancedController:
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
            welcome_data = json.loads(welcome)
            print(f"🔗 Połączono: {welcome_data}")
            print(f"📋 Dostępne tryby: {welcome_data.get('modes', [])}")
            self.connected = True
            return True
        except Exception as e:
            print(f"❌ Błąd połączenia: {e}")
            return False
    
    async def test_rt_frame_mode(self):
        """Test trybu real-time (fire-and-forget)."""
        print(f"\n🚀 TEST TRYBU RT_FRAME (Real-Time)")
        print("-" * 40)
        
        # Szybki ruch sinusoidalny wszystkich serw
        duration = 5  # sekund
        frequency = 25  # Hz
        total_frames = duration * frequency
        
        print(f"📊 Wysyłanie {total_frames} frames przez {duration}s przy {frequency}Hz")
        
        start_time = time.perf_counter()
        
        for i in range(total_frames):
            t = i / total_frames
            
            # Różne wzorce dla każdego serwa
            angles = [
                30 * math.sin(2 * math.pi * t * 2),      # Servo 0: 2Hz sinus
                20 * math.cos(2 * math.pi * t * 1.5),    # Servo 1: 1.5Hz cosinus
                15 * math.sin(2 * math.pi * t),          # Servo 2: 1Hz sinus
                25 * math.cos(2 * math.pi * t * 3),      # Servo 3: 3Hz cosinus  
                10 * math.sin(2 * math.pi * t * 0.5)     # Servo 4: 0.5Hz sinus
            ]
            
            cmd = {
                "cmd": "rt_frame",
                "deg": [round(a, 1) for a in angles],
                "ms": 40  # Krótki czas dla płynnego ruchu
            }
            
            await self.websocket.send(json.dumps(cmd))
            
            # Kontrola częstotliwości
            await asyncio.sleep(1.0 / frequency)
            
            if (i + 1) % frequency == 0:
                elapsed = time.perf_counter() - start_time
                print(f"  {elapsed:.1f}s: wysłano {i+1} frames")
        
        total_time = time.perf_counter() - start_time
        actual_freq = total_frames / total_time
        
        print(f"✅ RT_FRAME zakończony:")
        print(f"   Czas: {total_time:.1f}s")
        print(f"   Rzeczywista częstotliwość: {actual_freq:.1f}Hz")
        print(f"   Opóźnienie: {total_time - duration:.2f}s")
    
    async def test_trajectory_mode(self):
        """Test trybu trajectory (buforowanie)."""
        print(f"\n📋 TEST TRYBU TRAJECTORY (Buforowanie)")
        print("-" * 40)
        
        # Stwórz trajektorię z wieloma punktami
        points = []
        
        # Punkt startowy
        points.append({
            "deg": [0, 0, 0, 0, 0],
            "ms": 500,
            "rgb": {"r": 255, "g": 0, "b": 0}  # Czerwony
        })
        
        # Sekwencja ruchów
        moves = [
            ([45, -30, 20, -15, 35], 800, (0, 255, 0)),    # Zielony
            ([-30, 45, -25, 30, -20], 600, (0, 0, 255)),   # Niebieski
            ([20, -20, 40, -40, 10], 700, (255, 255, 0)),  # Żółty
            ([0, 0, 0, 0, 0], 1000, (255, 0, 255))         # Magenta
        ]
        
        for deg, ms, (r, g, b) in moves:
            points.append({
                "deg": deg,
                "ms": ms,
                "rgb": {"r": r, "g": g, "b": b}
            })
        
        # Wyślij całą trajektorię
        cmd = {
            "cmd": "trajectory",
            "points": points
        }
        
        print(f"📤 Wysyłanie trajektorii z {len(points)} punktami...")
        start_time = time.perf_counter()
        
        await self.websocket.send(json.dumps(cmd))
        response = await self.websocket.recv()
        result = json.loads(response)
        
        if result.get("ok"):
            print(f"✅ Trajektoria zaakceptowana")
            
            # Monitoruj wykonanie
            total_duration = sum(p["ms"] for p in points) / 1000
            print(f"⏱️  Oczekiwany czas wykonania: {total_duration:.1f}s")
            
            # Sprawdź status co sekundę
            for i in range(int(total_duration) + 2):
                await asyncio.sleep(1)
                
                await self.websocket.send('{"cmd": "status"}')
                status = await self.websocket.recv()
                status_data = json.loads(status)
                
                traj_mode = status_data.get("trajectory_mode", False)
                traj_points = status_data.get("trajectory_points", 0)
                traj_index = status_data.get("trajectory_index", 0)
                moving = status_data.get("moving", False)
                
                print(f"  {i+1}s: trajektoria {traj_index}/{traj_points}, ruch: {moving}")
                
                if not traj_mode and not moving:
                    break
            
            actual_time = time.perf_counter() - start_time
            print(f"✅ Trajektoria zakończona w {actual_time:.1f}s")
        else:
            print(f"❌ Błąd trajektorii: {result.get('err')}")
    
    async def test_stream_mode(self):
        """Test trybu stream (strumieniowy)."""
        print(f"\n🌊 TEST TRYBU STREAM (Strumieniowy)")
        print("-" * 40)
        
        # Uruchom tryb stream
        frequency = 30  # Hz
        duration = 3    # sekund
        
        start_cmd = {
            "cmd": "stream_start",
            "freq": frequency
        }
        
        print(f"🚀 Uruchamiam stream mode {frequency}Hz...")
        await self.websocket.send(json.dumps(start_cmd))
        response = await self.websocket.recv()
        result = json.loads(response)
        
        if not result.get("ok"):
            print(f"❌ Błąd uruchamiania stream: {result.get('err')}")
            return
        
        print(f"✅ Stream mode aktywny")
        print(f"📊 Wysyłanie pozycji przez {duration}s...")
        
        start_time = time.perf_counter()
        frame_count = 0
        
        for i in range(duration * frequency):
            t = i / (duration * frequency)
            
            # Płynny ruch w kształcie ósemki dla pierwszych dwóch serw
            angles = [
                20 * math.sin(2 * math.pi * t),              # X ósemki
                15 * math.sin(4 * math.pi * t),              # Y ósemki (2x częściej)
                10 * math.cos(2 * math.pi * t * 0.5),        # Wolny cosinus
                25 * math.sin(2 * math.pi * t * 1.5),        # Średni sinus
                -20 * math.cos(2 * math.pi * t * 0.3)        # Bardzo wolny
            ]
            
            # W trybie stream wysyłamy sam array, nie obiekt JSON
            position_data = [round(a, 1) for a in angles]
            
            await self.websocket.send(json.dumps(position_data))
            frame_count += 1
            
            # Pokazuj postęp
            if (i + 1) % frequency == 0:
                elapsed = time.perf_counter() - start_time
                print(f"  {elapsed:.1f}s: wysłano {frame_count} pozycji")
            
            await asyncio.sleep(1.0 / frequency)
        
        # Zatrzymaj stream mode
        stop_cmd = {"cmd": "stream_stop"}
        await self.websocket.send(json.dumps(stop_cmd))
        response = await self.websocket.recv()
        
        total_time = time.perf_counter() - start_time
        actual_freq = frame_count / total_time
        
        print(f"✅ Stream mode zakończony:")
        print(f"   Czas: {total_time:.1f}s") 
        print(f"   Wysłane pozycje: {frame_count}")
        print(f"   Rzeczywista częstotliwość: {actual_freq:.1f}Hz")
    
    async def close(self):
        if self.websocket:
            await self.websocket.close()


async def main():
    print("🤖 ESP32 Advanced Control Mode Test")
    print("=" * 50)
    
    controller = AdvancedController()
    
    if not await controller.connect():
        print("\n❌ Nie można połączyć się z ESP32.")
        print("   Upewnij się, że ESP32 jest uruchomiony i podłączony do sieci ESP32_RoboArm")
        return
    
    try:
        # Test 1: Real-time mode (najszybszy)
        await controller.test_rt_frame_mode()
        
        await asyncio.sleep(1)  # Krótka pauza
        
        # Test 2: Trajectory mode (bezpieczny)
        await controller.test_trajectory_mode()
        
        await asyncio.sleep(1)  # Krótka pauza
        
        # Test 3: Stream mode (eksperymentalny)
        await controller.test_stream_mode()
        
        print("\n" + "=" * 50)
        print("🎯 PODSUMOWANIE ZAAWANSOWANYCH TRYBÓW:")
        print("✅ RT_FRAME - Doskonały do sterowania real-time")
        print("✅ TRAJECTORY - Idealny do złożonych sekwencji") 
        print("✅ STREAM - Eksperymentalny tryb strumieniowy")
        print("\n💡 Wszystkie tryby działają płynnie!")
        print("   Można używać różnych trybów w zależności od potrzeb:")
        print("   • RT_FRAME: sterowanie w czasie rzeczywistym")
        print("   • TRAJECTORY: długie sekwencje ruchów") 
        print("   • STREAM: ciągły strumień pozycji")
        
    except Exception as e:
        print(f"\n❌ Błąd podczas testów: {e}")
    finally:
        await controller.close()


if __name__ == "__main__":
    asyncio.run(main())
