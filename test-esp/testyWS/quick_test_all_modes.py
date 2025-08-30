#!/usr/bin/env python3
"""
Szybki test wszystkich trybów ESP32 RoboArm.
Prosty przykład użycia każdego trybu.
"""

import asyncio
import json
import math
import websockets

async def test_all_modes():
    # Połącz z ESP32
    uri = "ws://192.168.4.1:81"
    
    try:
        async with websockets.connect(uri) as websocket:
            # Wiadomość powitalna
            welcome = await websocket.recv()
            print(f"✅ Połączono: {json.loads(welcome)}")
            
            # TEST 1: Standard frame
            print("\n🔧 Test 1: FRAME (standardowy)")
            cmd = {"cmd": "frame", "deg": [20, -15, 10, -5, 25], "ms": 800}
            await websocket.send(json.dumps(cmd))
            response = await websocket.recv()
            print(f"   Odpowiedź: {json.loads(response)}")
            await asyncio.sleep(1)
            
            # TEST 2: Real-time frame (10 szybkich ruchów)
            print("\n🚀 Test 2: RT_FRAME (real-time, 10 ruchów)")
            for i in range(10):
                angle = 20 * math.sin(i * 0.5)
                cmd = {"cmd": "rt_frame", "deg": [angle, -angle, 0, 0, 0], "ms": 100}
                await websocket.send(json.dumps(cmd))
                await asyncio.sleep(0.1)  # 10 Hz
            print("   Wysłano 10 rt_frame (bez odpowiedzi)")
            await asyncio.sleep(1)
            
            # TEST 3: Trajectory (sekwencja z kolorami)
            print("\n📋 Test 3: TRAJECTORY (sekwencja z RGB)")
            trajectory = {
                "cmd": "trajectory",
                "points": [
                    {"deg": [0,0,0,0,0], "ms": 300, "rgb": {"r": 255, "g": 0, "b": 0}},    # Czerwony
                    {"deg": [30,-20,15,-10,25], "ms": 600, "rgb": {"r": 0, "g": 255, "b": 0}}, # Zielony
                    {"deg": [-20,30,-15,20,-10], "ms": 500, "rgb": {"r": 0, "g": 0, "b": 255}}, # Niebieski
                    {"deg": [0,0,0,0,0], "ms": 400, "rgb": {"r": 255, "g": 255, "b": 255}}   # Biały
                ]
            }
            await websocket.send(json.dumps(trajectory))
            response = await websocket.recv()
            print(f"   Trajektoria: {json.loads(response)}")
            print("   Czekam na wykonanie sekwencji...")
            await asyncio.sleep(2.5)  # Całkowity czas trajektorii
            
            # TEST 4: Stream mode (ruch w kształcie ósemki)
            print("\n🌊 Test 4: STREAM (ruch w ósemce przez 3s)")
            
            # Uruchom stream
            await websocket.send('{"cmd": "stream_start", "freq": 20}')
            response = await websocket.recv()
            print(f"   Stream start: {json.loads(response)}")
            
            # Wyślij pozycje w kształcie ósemki
            for i in range(60):  # 3 sekundy * 20 Hz
                t = i / 60.0
                x = 25 * math.sin(2 * math.pi * t)          # X ósemki
                y = 15 * math.sin(4 * math.pi * t)          # Y ósemki (2x częściej)
                z = 10 * math.cos(2 * math.pi * t * 0.5)    # Wolny ruch Z
                
                position = [x, y, z, 0, 0]
                await websocket.send(json.dumps(position))
                await asyncio.sleep(0.05)  # 20 Hz
            
            # Zatrzymaj stream
            await websocket.send('{"cmd": "stream_stop"}')
            response = await websocket.recv()
            print(f"   Stream stop: {json.loads(response)}")
            
            # Powrót do pozycji domowej
            print("\n🏠 Powrót do pozycji domowej")
            cmd = {"cmd": "home", "ms": 1000, "rgb": {"r": 0, "g": 255, "b": 0}}
            await websocket.send(json.dumps(cmd))
            response = await websocket.recv()
            print(f"   Home: {json.loads(response)}")
            
            print("\n✅ Test wszystkich trybów zakończony pomyślnie!")
            
    except Exception as e:
        print(f"❌ Błąd: {e}")
        print("   Sprawdź czy ESP32 jest uruchomiony i jesteś połączony z WiFi ESP32_RoboArm")

if __name__ == "__main__":
    print("🤖 Szybki test wszystkich trybów ESP32 RoboArm")
    print("=" * 50)
    asyncio.run(test_all_modes())
