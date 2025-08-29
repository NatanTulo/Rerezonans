#!/usr/bin/env python3
"""Testowy klient serial JSON dla firmware'u robota.

Wysyła przykładowe polecenia JSON i drukuje odpowiedzi.
"""

import argparse
import json
import sys
import time
from typing import List

import serial


def send_and_recv(ser: serial.Serial, obj: dict, read_timeout: float = 1.0) -> List[str]:
    s = json.dumps(obj, separators=(",", ":"))
    ser.write((s + "\n").encode("utf-8"))
    ser.flush()
    # read lines until timeout
    deadline = time.time() + read_timeout
    lines = []
    while time.time() < deadline:
        try:
            line = ser.readline()
        except Exception:
            break
        if not line:
            # no data ready
            continue
        try:
            decoded = line.decode("utf-8", errors="replace").rstrip("\r\n")
        except Exception:
            decoded = repr(line)
        lines.append(decoded)
        # quick heuristic: stop if an "ok" or "err" JSON seen
        if decoded.startswith("{") and ("\"ok\"" in decoded or "\"err\"" in decoded or "ready" in decoded or "pong" in decoded):
            break
    return lines


def run_sequence(ser: serial.Serial):
    seq = [
        ("ping", {"cmd": "ping"}),
        ("home (800ms, led=0)", {"cmd": "home", "ms": 800, "led": 0}),
        ("led=128", {"cmd": "led", "val": 128}),
        ("freq=50.0", {"cmd": "freq", "hz": 50.0}),
        (
            "config ch0",
            {"cmd": "config", "ch": 0, "min_us": 900, "max_us": 2100, "offset_us": 0, "invert": False},
        ),
        (
            "frame sample",
            {"cmd": "frame", "deg": [0, 10, -20, 5, 0], "ms": 200, "led": 200},
        ),
        ("bad led (out of range)", {"cmd": "led", "val": 999}),
        ("unknown cmd", {"cmd": "nope"}),
    ]

    for name, cmd in seq:
        print("---\nWysyłam:", name, json.dumps(cmd))
        lines = send_and_recv(ser, cmd, read_timeout=1.0)
        if not lines:
            print("Brak odpowiedzi (timeout)")
        else:
            for l in lines:
                print("<-", l)
        time.sleep(0.1)


def open_serial(port: str, baud: int, timeout: float):
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=0.1)
        # drain any initial available data
        time.sleep(0.05)
        while ser.in_waiting:
            _ = ser.readline()
        return ser
    except serial.SerialException as e:
        print("Błąd otwarcia portu:", e, file=sys.stderr)
        sys.exit(2)


def main():
    p = argparse.ArgumentParser(description="Testowy klient JSON dla robota przez port szeregowy")
    # make port optional on the command-line; we'll validate it after parsing
    p.add_argument("port", nargs="?", help="port szeregowy, np. /dev/ttyUSB0")
    p.add_argument("--baud", type=int, default=115200, help="prędkość transmisji (domyślnie 115200)")
    p.add_argument("--dry", action="store_true", help="nie wysyłaj, tylko pokaż sekwencję")
    args = p.parse_args()

    # require `port` unless --dry was requested
    if not args.dry and not args.port:
        p.error("port is required unless --dry is set")

    seq_preview = [
        {"cmd": "ping"},
        {"cmd": "home", "ms": 800, "led": 0},
        {"cmd": "led", "val": 128},
        {"cmd": "freq", "hz": 50.0},
        {"cmd": "config", "ch": 0, "min_us": 900, "max_us": 2100, "offset_us": 0, "invert": False},
        {"cmd": "frame", "deg": [0, 10, -20, 5, 0], "ms": 200, "led": 200},
        {"cmd": "led", "val": 999},
        {"cmd": "nope"},
    ]

    if args.dry:
        print("Sekwencja do wysłania:")
        for o in seq_preview:
            print(json.dumps(o))
        return

    ser = open_serial(args.port, args.baud, timeout=0.1)
    print("Port otwarty:", ser.port, "baud:", args.baud)
    try:
        run_sequence(ser)
    finally:
        ser.close()


if __name__ == "__main__":
    main()
