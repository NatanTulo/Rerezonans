#!/usr/bin/env python3
"""
Test opóźnień WebSocket ESP32 RoboArm.
Mierzy round-trip time dla różnych typów poleceń.
"""

import argparse
import asyncio
import json
import time
import statistics
from typing import List, Tuple

import websockets
from websockets.exceptions import ConnectionClosed


class LatencyTester:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.uri = f"ws://{host}:{port}"
        self.websocket = None
        
    async def connect(self):
        """Połączenie z ESP32"""
        try:
            self.websocket = await websockets.connect(self.uri)
            print(f"Połączono z {self.uri}")
            
            # Odbierz wiadomość powitalną
            welcome = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            print(f"Wiadomość powitalna: {welcome}")
            return True
        except Exception as e:
            print(f"Błąd połączenia: {e}")
            return False
    
    async def send_and_measure(self, cmd: dict) -> float:
        """Wyślij polecenie i zmierz czas odpowiedzi"""
        if not self.websocket:
            return -1.0
            
        try:
            start_time = time.time()
            
            # Wyślij polecenie
            await self.websocket.send(json.dumps(cmd))
            
            # Odbierz odpowiedź
            response = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
            
            end_time = time.time()
            latency = (end_time - start_time) * 1000  # ms
            
            return latency
            
        except asyncio.TimeoutError:
            return -1.0  # Timeout
        except Exception as e:
            print(f"Błąd komunikacji: {e}")
            return -1.0
    
    async def ping_test(self, count: int = 100) -> List[float]:
        """Test ping - prosty round-trip"""
        print(f"\n=== Test PING ({count} prób) ===")
        latencies = []
        
        for i in range(count):
            latency = await self.send_and_measure({"cmd": "ping"})
            if latency > 0:
                latencies.append(latency)
                print(f"Ping {i+1:3d}: {latency:6.2f}ms", end="\r")
            else:
                print(f"Ping {i+1:3d}: TIMEOUT", end="\r")
            
            await asyncio.sleep(0.01)  # 10ms pauza
        
        print()  # Nowa linia
        return latencies
    
    async def frame_test(self, count: int = 50) -> List[float]:
        """Test frame commands - bardziej realistyczne"""
        print(f"\n=== Test FRAME ({count} prób) ===")
        latencies = []
        
        for i in range(count):
            # Losowe kąty dla testowania
            angles = [
                (i * 2) % 180 - 90,  # -90 do +90
                (i * 3) % 180 - 90,
                (i * 5) % 180 - 90,
                (i * 7) % 180 - 90,
                (i * 11) % 180 - 90
            ]
            
            cmd = {
                "cmd": "frame",
                "deg": angles,
                "ms": 50  # Szybki ruch
            }
            
            latency = await self.send_and_measure(cmd)
            if latency > 0:
                latencies.append(latency)
                print(f"Frame {i+1:2d}: {latency:6.2f}ms", end="\r")
            else:
                print(f"Frame {i+1:2d}: TIMEOUT", end="\r")
            
            await asyncio.sleep(0.02)  # 20ms pauza
        
        print()  # Nowa linia
        return latencies
    
    async def frequency_test(self, frequency: float, duration: float = 10.0) -> List[float]:
        """Test przy stałej częstotliwości"""
        period = 1.0 / frequency
        print(f"\n=== Test częstotliwości {frequency}Hz przez {duration}s ===")
        print(f"Okres: {period*1000:.1f}ms")
        
        latencies = []
        start_time = time.time()
        frame_count = 0
        
        while time.time() - start_time < duration:
            frame_start = time.time()
            
            # Prosty ruch sinusoidalny
            t = time.time() - start_time
            angle = 30 * (t % 4.0 - 2.0) / 2.0  # -30 do +30 stopni
            
            cmd = {
                "cmd": "frame", 
                "deg": [angle, -angle/2, angle/3, 0, 0],
                "ms": int(period * 1000 * 0.8)  # 80% okresu na ruch
            }
            
            latency = await self.send_and_measure(cmd)
            if latency > 0:
                latencies.append(latency)
            
            frame_count += 1
            print(f"Frame {frame_count:3d}: {latency:6.2f}ms", end="\r")
            
            # Utrzymaj częstotliwość
            frame_duration = time.time() - frame_start
            sleep_time = max(0, period - frame_duration)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        print()
        return latencies
    
    def analyze_results(self, latencies: List[float], test_name: str):
        """Analiza wyników testów"""
        if not latencies:
            print(f"{test_name}: Brak pomyślnych pomiarów!")
            return
        
        avg = statistics.mean(latencies)
        median = statistics.median(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        stdev = statistics.stdev(latencies) if len(latencies) > 1 else 0
        
        # Percentyle
        sorted_lat = sorted(latencies)
        p95 = sorted_lat[int(0.95 * len(sorted_lat))]
        p99 = sorted_lat[int(0.99 * len(sorted_lat))]
        
        # Procent szybkich odpowiedzi
        fast_5ms = sum(1 for x in latencies if x < 5) / len(latencies) * 100
        fast_10ms = sum(1 for x in latencies if x < 10) / len(latencies) * 100
        fast_20ms = sum(1 for x in latencies if x < 20) / len(latencies) * 100
        
        print(f"\n=== Wyniki {test_name} ===")
        print(f"Próbek: {len(latencies)}")
        print(f"Średnia: {avg:.2f}ms")
        print(f"Mediana: {median:.2f}ms")
        print(f"Min/Max: {min_lat:.2f}ms / {max_lat:.2f}ms")
        print(f"Odch. std: {stdev:.2f}ms")
        print(f"95%: {p95:.2f}ms")
        print(f"99%: {p99:.2f}ms")
        print(f"< 5ms: {fast_5ms:.1f}%")
        print(f"< 10ms: {fast_10ms:.1f}%")
        print(f"< 20ms: {fast_20ms:.1f}%")
        
        # Ocena wydajności
        if avg < 5 and fast_10ms > 95:
            print("✅ DOSKONAŁA wydajność - idealne do sterowania w czasie rzeczywistym")
        elif avg < 10 and fast_20ms > 90:
            print("✅ DOBRA wydajność - nadaje się do sterowania w czasie rzeczywistym")
        elif avg < 20 and fast_20ms > 70:
            print("⚠️ ŚREDNIA wydajność - ograniczone sterowanie w czasie rzeczywistym")
        else:
            print("❌ SŁABA wydajność - tylko sterowanie pozycyjne")
    
    async def close(self):
        """Zamknij połączenie"""
        if self.websocket:
            await self.websocket.close()


async def main():
    parser = argparse.ArgumentParser(description="Test opóźnień WebSocket ESP32")
    parser.add_argument("--host", default="192.168.4.1", help="IP ESP32")
    parser.add_argument("--port", type=int, default=81, help="Port WebSocket")
    parser.add_argument("--ping-count", type=int, default=100, help="Liczba ping testów")
    parser.add_argument("--frame-count", type=int, default=50, help="Liczba frame testów")
    parser.add_argument("--frequency", type=float, help="Test konkretnej częstotliwości (Hz)")
    parser.add_argument("--duration", type=float, default=10.0, help="Czas testu częstotliwości (s)")
    
    args = parser.parse_args()
    
    tester = LatencyTester(args.host, args.port)
    
    try:
        if not await tester.connect():
            return
        
        if args.frequency:
            # Test konkretnej częstotliwości
            latencies = await tester.frequency_test(args.frequency, args.duration)
            tester.analyze_results(latencies, f"Częstotliwość {args.frequency}Hz")
        else:
            # Standardowe testy
            # 1. Test ping
            ping_latencies = await tester.ping_test(args.ping_count)
            tester.analyze_results(ping_latencies, "PING")
            
            await asyncio.sleep(1)
            
            # 2. Test frame
            frame_latencies = await tester.frame_test(args.frame_count)
            tester.analyze_results(frame_latencies, "FRAME")
            
            await asyncio.sleep(1)
            
            # 3. Testy częstotliwości
            for freq in [10, 20, 30, 50]:
                print(f"\n{'='*50}")
                latencies = await tester.frequency_test(freq, 5.0)
                tester.analyze_results(latencies, f"{freq}Hz")
                await asyncio.sleep(0.5)
        
    except KeyboardInterrupt:
        print("\nTest przerwany przez użytkownika")
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
