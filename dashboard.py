import argparse
import ctypes
import json
import os
import shutil
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


def walk(node, path, out):
    path = path + [node.get("Text", "")]
    if node.get("Value"):
        out.append((" / ".join(path), node["Value"]))
    for child in node.get("Children", []):
        walk(child, path, out)

RETRY_SECONDS = 10
sensors_down_until = 0.0


def sensors(url):
    global sensors_down_until
    if time.monotonic() < sensors_down_until:
        return []
    try:
        with urllib.request.urlopen(url, timeout=0.5) as r:
            tree = json.load(r)
    except (OSError, ValueError):
        sensors_down_until = time.monotonic() + RETRY_SECONDS
        return []
    out = []
    walk(tree, [], out)
    return out

def find_value(data, ending):
    for path, value in data:
        if path.endswith(ending):
            try:
                return float(value.split()[0].replace(",", "."))
            except (ValueError, IndexError):
                continue
    return None

def fmt_temp(value):
    return "  n/a" if value is None else f"{value:5.1f} °C"

def find_value(data, ending):
    for path, value in data:
        if path.endswith(ending):
            try:
                return float(value.split()[0].replace(",", "."))
            except (ValueError, IndexError):
                continue
    return None


def fmt_temp(value):
    return "  n/a" if value is None else f"{value:5.1f} °C"


def parse_args():
    p = argparse.ArgumentParser(description="Terminal-dashboard til CPU, RAM, GPU og disk")
    p.add_argument("-i", "--interval", type=float, default=1.0, help="sekunder mellem opdateringer")
    p.add_argument("--url", default="http://localhost:8085/data.json", help="LibreHardwareMonitor data.json")
    p.add_argument("--disk", default="C:\\", help="drev der vises i disk-panelet")
    return p.parse_args()
 
def main():
    args = parse_args()
    os.system("")
    sys.stdout.write("\x1b[?25l\x1b[2J")

    HIST_MAX = 500
    cpu_hist = [0.0] * HIST_MAX
    ram_hist = [0.0] * HIST_MAX
    prev_idle, prev_total = cpu_times()
    try:
        while True:
            time.sleep(args.interval)
            idle, total = cpu_times()
            d_total = total - prev_total
            cpu = 100 * (1 - (idle - prev_idle) / d_total) if d_total else 0.0
            prev_idle, prev_total = idle, total

            ram, used, ram_total = ram_usage()

            cpu_hist = cpu_hist[1:] + [cpu]
            ram_hist = ram_hist[1:] + [ram]

            data = sensors(args.url)
            cpu_temp = find_value(data, "Temperatures / CPU Package")

            gpu_load = find_value(data, "Load / GPU Core")
            gpu_temp = find_value(data, "Temperatures / GPU Core")

            disk = shutil.disk_usage(args.disk)
            disk_pct = disk.used / disk.total * 100

            cols = shutil.get_terminal_size().columns
            width = max(10, min(cols - 40, 100))
            hist_len = max(10, min(cols - 8, HIST_MAX))

            gb = 1024 ** 3
            out = [
                "\x1b[H\x1b[1m  TERMINAL-DASHBOARD\x1b[0m   (Ctrl+C for at stoppe)",
                "",
                f"  CPU  {color(cpu)}{bar(cpu, width)}{RESET} {cpu:5.1f} %  {fmt_temp(cpu_temp)}",
                f"       {color(cpu)}{sparkline(cpu_hist[-hist_len:])}{RESET}",
                "",
                f"  RAM  {color(ram)}{bar(ram, width)}{RESET} {ram:5.1f} %  "
                f"({used / gb:.1f} / {ram_total / gb:.1f} GB)",
                f"       {color(ram)}{sparkline(ram_hist[-hist_len:])}{RESET}",
                "",
            ]
            if gpu_load is None:
                out.append("  GPU  n/a (start LibreHardwareMonitor med Remote Web Server)")
            else:
                out.append(f"  GPU  {color(gpu_load)}{bar(gpu_load, width)}{RESET} "
                           f"{gpu_load:5.1f} %  {fmt_temp(gpu_temp)}")
            out += [
                "",
                f"  DISK {color(disk_pct)}{bar(disk_pct, width)}{RESET} {disk_pct:5.1f} %  "
                f"({disk.used / gb:.0f} / {disk.total / gb:.0f} GB)",
            ]
            sys.stdout.write("\n".join(line + "\x1b[K" for line in out) + "\x1b[J")
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?25h\n")
if __name__ == "__main__":
    main()
