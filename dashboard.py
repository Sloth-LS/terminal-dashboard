import ctypes
import json
import os
import sys
import time
import urllib.request
from ctypes import wintypes

RESET = "\x1b[0m"
kernel32 = ctypes.windll.kernel32


def bar(pct, width=40):
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


BLOCKS = " ▁▂▃▄▅▆▇█"


def sparkline(values):
    return "".join(BLOCKS[round(v / 100 * 8)] for v in values)


def color(pct):
    if pct > 80:
        return "\x1b[31m"  # red
    if pct > 50:
        return "\x1b[33m"  # yellow
    return "\x1b[32m"      # green


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def ram_usage():
    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(m)
    kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    used = m.ullTotalPhys - m.ullAvailPhys
    return used / m.ullTotalPhys * 100, used, m.ullTotalPhys


class FILETIME(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]


def to_int(ft):
    return (ft.high << 32) | ft.low


def cpu_times():
    idle_time = FILETIME()
    kernel_time = FILETIME()
    user_time = FILETIME()
    kernel32.GetSystemTimes(ctypes.byref(idle_time), ctypes.byref(kernel_time), ctypes.byref(user_time))
    return to_int(idle_time), to_int(kernel_time) + to_int(user_time)


URL = "http://localhost:8085/data.json"


def walk(node, path, out):
    path = path + [node.get("Text", "")]
    if node.get("Value"):
        out.append((" / ".join(path), node["Value"]))
    for child in node.get("Children", []):
        walk(child, path, out)


def sensors():
    try:
        with urllib.request.urlopen(URL, timeout=0.5) as r:
            tree = json.load(r)
    except OSError:
        return []
    out = []
    walk(tree, [], out)
    return out


def find_value(data, ending):
    for path, value in data:
        if path.endswith(ending):
            return float(value.split()[0].replace(",", "."))
    return None


def main():
    os.system("")
    sys.stdout.write("\x1b[?25l\x1b[2J")  # skjul markør, ryd skærm én gang
    cpu_hist = [0.0] * 60
    ram_hist = [0.0] * 60
    prev_idle, prev_total = cpu_times()
    try:
        while True:
            time.sleep(1)
            idle, total = cpu_times()
            d_total = total - prev_total
            cpu = 100 * (1 - (idle - prev_idle) / d_total) if d_total else 0.0
            prev_idle, prev_total = idle, total

            ram, used, ram_total = ram_usage()

            cpu_hist = cpu_hist[1:] + [cpu]
            ram_hist = ram_hist[1:] + [ram]

            gb = 1024 ** 3
            out = [
                "\x1b[H\x1b[1m  TERMINAL-DASHBOARD\x1b[0m   (Ctrl+C for at stoppe)",
                "",
                f"  CPU {color(cpu)}{bar(cpu)}{RESET} {cpu:5.1f} %",
                f"      {color(cpu)}{sparkline(cpu_hist)}{RESET}",
                "",
                f"  RAM {color(ram)}{bar(ram)}{RESET} {ram:5.1f} %  "
                f"({used / gb:.1f} / {ram_total / gb:.1f} GB)",
                f"      {color(ram)}{sparkline(ram_hist)}{RESET}",
            ]
            sys.stdout.write("\n".join(line + "\x1b[K" for line in out))
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?25h\n")  # vis markøren igen


if __name__ == "__main__":
    main()
    eval
    frozenset
    sorted