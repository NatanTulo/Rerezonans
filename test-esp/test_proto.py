#!/usr/bin/env python3
"""Testowy klient WebSocket JSON dla firmware'u robota.

Wysyła przykładowe polecenia JSON przez WebSocket i drukuje odpowiedzi.
Testuje wszystkie tryby sterowania:
- frame: standardowy tryb z potwierdzeniem
- rt_frame: real-time (fire-and-forget)  
- trajectory: buforowanie sekwencji na ESP32
- stream: tryb strumieniowy z kompaktowymi danymi
"""

import argparse
import json
import sys
import time
import asyncio
from typing import List

import websockets
from websockets.exceptions import ConnectionClosed


async def test_stream_mode(websocket):
    """Testuje tryb stream - wysyła kilka pozycji w trybie strumieniowym."""
    print("\n=== TEST STREAM MODE ===")
    
    # Wysyłanie pozycji w trybie stream (bez polecenia start - już wysłane)
    import math
    stream_positions = []
    for i in range(5):
        t = i / 4.0  # 0 do 1
        angle = 20 * math.sin(2 * math.pi * t)
        pos = [angle, -angle, 0, 0, 0]
        stream_positions.append(pos)
    
    for i, pos in enumerate(stream_positions):
        print(f"Wysyłam pozycję stream {i+1}: {pos}")
        await websocket.send(json.dumps(pos, separators=(",", ":")))
        await asyncio.sleep(0.2)  # 5 Hz
    
    # Zatrzymaj stream mode
    print("Zatrzymuję stream mode...")
    stop_cmd = {"cmd": "stream_stop"}
    lines = await send_and_recv(websocket, stop_cmd, read_timeout=2.0)
    for l in lines:
        print("<-", l)


async def send_and_recv(websocket, obj: dict, read_timeout: float = 3.0) -> List[str]:
    """Wysyła JSON przez WebSocket i odbiera odpowiedzi."""
    s = json.dumps(obj, separators=(",", ":"))
    await websocket.send(s)
    
    responses = []
    try:
        # Czekaj na odpowiedź
        response = await asyncio.wait_for(websocket.recv(), timeout=read_timeout)
        responses.append(response)
    except asyncio.TimeoutError:
        responses.append("TIMEOUT")
    except ConnectionClosed:
        responses.append("CONNECTION_CLOSED")
    
    return responses


async def run_sequence(websocket):
    """Uruchamia sekwencję testowych poleceń."""
    seq = [
        ("ping", {"cmd": "ping"}),
        ("home (800ms, led=128, rgb=green)", {"cmd": "home", "ms": 800, "led": 128, "rgb": {"r": 0, "g": 255, "b": 0}}),
        ("led=64", {"cmd": "led", "val": 64}),
        ("rgb=red", {"cmd": "rgb", "r": 255, "g": 0, "b": 0}),
        ("frame sample with RGB blue", {"cmd": "frame", "deg": [10, -20, 15, -5, 30], "ms": 1000, "led": 200, "rgb": {"r": 0, "g": 0, "b": 255}}),
        ("status request", {"cmd": "status"}),
        ("rt_frame test (fire-and-forget)", {"cmd": "rt_frame", "deg": [20, -10, 0, 15, -25], "ms": 100}),
        ("led=256", {"cmd": "led", "val": 256}),
        ("trajectory test", {"cmd": "trajectory", "points": [
            {"deg": [0, 0, 0, 0, 0], "ms": 300, "rgb": {"r": 255, "g": 0, "b": 0}},
            {"deg": [30, -20, 15, -10, 25], "ms": 500, "rgb": {"r": 0, "g": 255, "b": 0}},
            {"deg": [0, 0, 0, 0, 0], "ms": 300, "rgb": {"r": 0, "g": 0, "b": 255}}
        ]}),
        ("rgb=purple", {"cmd": "rgb", "r": 128, "g": 0, "b": 128}),
        ("stream test start", {"cmd": "stream_start", "freq": 10}),
        ("home again", {"cmd": "home", "ms": 500, "rgb": {"r": 0, "g": 255, "b": 0}}),
        ("led=64", {"cmd": "led", "val": 64})
    ]

    for name, cmd in seq:
        print("---\nWysyłam:", name, json.dumps(cmd))
        
        # rt_frame nie zwraca odpowiedzi (fire-and-forget)
        if cmd.get("cmd") == "rt_frame":
            await websocket.send(json.dumps(cmd, separators=(",", ":")))
            print("<- (brak odpowiedzi - fire-and-forget)")
            await asyncio.sleep(0.2)
            continue
            
        lines = await send_and_recv(websocket, cmd, read_timeout=3.0)
        if not lines:
            print("Brak odpowiedzi (timeout)")
        else:
            for l in lines:
                print("<-", l)
        
        # Dłuższa pauza po trajectory
        if cmd.get("cmd") == "trajectory":
            print("Czekam na wykonanie trajektorii...")
            await asyncio.sleep(2.0)
        else:
            await asyncio.sleep(0.5)  # Krótka pauza między poleceniami
    
    # Test stream mode
    await test_stream_mode(websocket)


async def connect_websocket(host: str, port: int):
    """Nawiązuje połączenie WebSocket z ESP32."""
    uri = f"ws://{host}:{port}"
    try:
        websocket = await websockets.connect(uri)
        print(f"Połączono z {uri}")
        return websocket
    except Exception as e:
        print(f"Błąd połączenia z {uri}: {e}", file=sys.stderr)
        sys.exit(2)


async def main():
    p = argparse.ArgumentParser(description="Testowy klient WebSocket JSON dla robota ESP32")
    p.add_argument("--host", default="192.168.4.1", help="adres IP ESP32 (domyślnie 192.168.4.1)")
    p.add_argument("--port", type=int, default=81, help="port WebSocket (domyślnie 81)")
    p.add_argument("--dry", action="store_true", help="nie łącz się, tylko pokaż sekwencję")
    args = p.parse_args()

    seq_preview = [
        {"cmd": "ping"},
        {"cmd": "home", "ms": 800, "led": 128, "rgb": {"r": 0, "g": 255, "b": 0}},
        {"cmd": "led", "val": 64},
        {"cmd": "rgb", "r": 255, "g": 0, "b": 0},
        {"cmd": "frame", "deg": [10, -20, 15, -5, 30], "ms": 1000, "led": 200, "rgb": {"r": 0, "g": 0, "b": 255}},
        {"cmd": "status"},
        {"cmd": "rt_frame", "deg": [20, -10, 0, 15, -25], "ms": 100},
        {"cmd": "trajectory", "points": [
            {"deg": [0, 0, 0, 0, 0], "ms": 300, "rgb": {"r": 255, "g": 0, "b": 0}},
            {"deg": [30, -20, 15, -10, 25], "ms": 500, "rgb": {"r": 0, "g": 255, "b": 0}},
            {"deg": [0, 0, 0, 0, 0], "ms": 300, "rgb": {"r": 0, "g": 0, "b": 255}}
        ]},
        {"cmd": "stream_start", "freq": 10},
        [20, -20, 0, 0, 0],  # przykład danych stream
        [0, 0, 0, 0, 0],     # przykład danych stream
        {"cmd": "stream_stop"},
    ]

    if args.dry:
        print("Sekwencja do wysłania:")
        for o in seq_preview:
            print(json.dumps(o))
        return

    websocket = await connect_websocket(args.host, args.port)
    try:
        # Czekaj na wiadomość powitalną
        welcome = await websocket.recv()
        print("Wiadomość powitalna:", welcome)
        
        await run_sequence(websocket)
        
        # Nasłuchuj na dodatkowe wiadomości przez krótki czas
        print("\nNasłuchiwanie na dodatkowe wiadomości (5 sekund)...")
        try:
            count = 0
            deadline = time.time() + 5.0  # 5 sekund zamiast nieskończoności
            while time.time() < deadline and count < 10:  # max 10 wiadomości
                remaining = deadline - time.time()
                msg = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                print("Otrzymano:", msg)
                count += 1
        except asyncio.TimeoutError:
            print("Timeout - kończenie nasłuchiwania")
            
    except ConnectionClosed:
        print("Połączenie zostało zamknięte")
    finally:
        await websocket.close()


if __name__ == "__main__":
    asyncio.run(main())
