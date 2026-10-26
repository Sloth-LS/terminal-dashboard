import argparse
import base64
import configparser
import ctypes
import json
import msvcrt
import os
import re
import shutil
import sys
import time
import urllib.request
from ctypes import wintypes

RESET = "\x1b[0m"
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32
pdh = ctypes.windll.pdh


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


# --- GPU temperatur (same as Task Manager) ------------------------------------

class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class ADAPTERINFO(ctypes.Structure):
    _fields_ = [
        ("hAdapter", ctypes.c_uint),
        ("AdapterLuid", LUID),
        ("NumOfSources", ctypes.c_ulong),
        ("bPrecisePresentRegionsPreferred", wintypes.BOOL),
    ]


class ENUMADAPTERS2(ctypes.Structure):
    _fields_ = [("NumAdapters", ctypes.c_ulong), ("pAdapters", ctypes.POINTER(ADAPTERINFO))]


class QUERYADAPTERINFO(ctypes.Structure):
    _fields_ = [
        ("hAdapter", ctypes.c_uint),
        ("Type", ctypes.c_int),
        ("pPrivateDriverData", ctypes.c_void_p),
        ("PrivateDriverDataSize", ctypes.c_uint),
    ]


class ADAPTER_PERFDATA(ctypes.Structure):
    _fields_ = [
        ("PhysicalAdapterIndex", ctypes.c_uint32),
        ("MemoryFrequency", ctypes.c_ulonglong),
        ("MaxMemoryFrequency", ctypes.c_ulonglong),
        ("MaxMemoryFrequencyOC", ctypes.c_ulonglong),
        ("MemoryBandwidth", ctypes.c_ulonglong),
        ("PCIEBandwidth", ctypes.c_ulonglong),
        ("FanRPM", ctypes.c_ulong),
        ("Power", ctypes.c_ulong),
        ("Temperature", ctypes.c_ulong),  # 1/10 temperature
        ("PowerStateOverride", ctypes.c_ubyte),
    ]


def gpu_adapters():
    e = ENUMADAPTERS2()
    gdi32.D3DKMTEnumAdapters2(ctypes.byref(e))  # first call: how many?
    adapters = (ADAPTERINFO * e.NumAdapters)()
    e.pAdapters = adapters
    gdi32.D3DKMTEnumAdapters2(ctypes.byref(e))
    return [a.hAdapter for a in adapters]


def gpu_temperature(adapters):
    for handle in adapters:
        pd = ADAPTER_PERFDATA()
        q = QUERYADAPTERINFO(handle, 62, ctypes.cast(ctypes.byref(pd), ctypes.c_void_p), ctypes.sizeof(pd))
        if gdi32.D3DKMTQueryAdapterInfo(ctypes.byref(q)) == 0 and pd.Temperature:
            return pd.Temperature / 10
    return None


# --- GPU load (Windows performance counters) ----------------------------------

class PDH_FMT_COUNTERVALUE(ctypes.Structure):
    _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]


class PDH_FMT_COUNTERVALUE_ITEM(ctypes.Structure):
    _fields_ = [("szName", wintypes.LPWSTR), ("FmtValue", PDH_FMT_COUNTERVALUE)]


def gpu_counter():
    query = ctypes.c_void_p()
    counter = ctypes.c_void_p()
    pdh.PdhOpenQueryW(None, None, ctypes.byref(query))
    pdh.PdhAddEnglishCounterW(query, "\\GPU Engine(*engtype_3D)\\Utilization Percentage", None, ctypes.byref(counter))
    pdh.PdhCollectQueryData(query)
    return query, counter


def gpu_usage(query, counter):
    pdh.PdhCollectQueryData(query)
    size = wintypes.DWORD(0)
    count = wintypes.DWORD(0)
    status = pdh.PdhGetFormattedCounterArrayW(counter, 0x200, ctypes.byref(size), ctypes.byref(count), None)
    if status & 0xFFFFFFFF != 0x800007D2:
        return None
    buf = ctypes.create_string_buffer(size.value)
    pdh.PdhGetFormattedCounterArrayW(counter, 0x200, ctypes.byref(size), ctypes.byref(count), buf)
    items = ctypes.cast(buf, ctypes.POINTER(PDH_FMT_COUNTERVALUE_ITEM))
    return min(sum(items[i].FmtValue.doubleValue for i in range(count.value)), 100.0)


# --- Network ---

def counter_sum(counter):
    size = wintypes.DWORD(0)
    count = wintypes.DWORD(0)
    status = pdh.PdhGetFormattedCounterArrayW(counter, 0x200, ctypes.byref(size), ctypes.byref(count), None)
    if status & 0xFFFFFFFF != 0x800007D2:
        return 0.0
    buf = ctypes.create_string_buffer(size.value)
    pdh.PdhGetFormattedCounterArrayW(counter, 0x200, ctypes.byref(size), ctypes.byref(count), buf)
    items = ctypes.cast(buf, ctypes.POINTER(PDH_FMT_COUNTERVALUE_ITEM))
    return sum(items[i].FmtValue.doubleValue for i in range(count.value))


def net_counters():
    query = ctypes.c_void_p()
    recv = ctypes.c_void_p()
    sent = ctypes.c_void_p()
    pdh.PdhOpenQueryW(None, None, ctypes.byref(query))
    pdh.PdhAddEnglishCounterW(query, "\\Network Interface(*)\\Bytes Received/sec", None, ctypes.byref(recv))
    pdh.PdhAddEnglishCounterW(query, "\\Network Interface(*)\\Bytes Sent/sec", None, ctypes.byref(sent))
    pdh.PdhCollectQueryData(query)
    return query, recv, sent


def net_speed(query, recv, sent):
    pdh.PdhCollectQueryData(query)
    return counter_sum(recv), counter_sum(sent)


def fmt_speed(b):
    if b >= 1024 ** 2:
        return f"{b / 1024 ** 2:6.2f} MB/s"
    return f"{b / 1024:6.1f} KB/s"


def fmt_temp(value):
    return "  n/a" if value is None else f"{value:5.1f} °C"


def uptime_text():
    kernel32.GetTickCount64.restype = ctypes.c_ulonglong
    seconds = kernel32.GetTickCount64() // 1000
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    return f"{days} d {hours} h {minutes} min"


def fixed_drives():
    mask = kernel32.GetLogicalDrives()
    drives = []
    for i in range(26):
        if mask & (1 << i):
            root = f"{chr(65 + i)}:\\"
            if kernel32.GetDriveTypeW(root) == 3:  # 3 = fixed disk
                drives.append(root)
    return drives


ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
CYAN = "\x1b[36m"
DIM = "\x1b[2m"
BOLD = "\x1b[1m"

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# Big digits for the clock: each character is 5 rows high and 3 wide
FONT = {
    "0": ["███", "█ █", "█ █", "█ █", "███"],
    "1": [" █ ", "██ ", " █ ", " █ ", "███"],
    "2": ["███", "  █", "███", "█  ", "███"],
    "3": ["███", "  █", "███", "  █", "███"],
    "4": ["█ █", "█ █", "███", "  █", "  █"],
    "5": ["███", "█  ", "███", "  █", "███"],
    "6": ["███", "█  ", "███", "█ █", "███"],
    "7": ["███", "  █", "  █", "  █", "  █"],
    "8": ["███", "█ █", "███", "█ █", "███"],
    "9": ["███", "█ █", "███", "  █", "███"],
    ":": ["   ", " ▀ ", "   ", " ▄ ", "   "],
}


def visible_len(text):
    return len(ANSI.sub("", text))


def pad(text, width):
    return text + " " * (width - visible_len(text))


def big_clock(text):
    return [" ".join(FONT[ch][row] for ch in text) for row in range(5)]


def tall_graph(values, height):
    rows = []
    for row in range(height):
        level_floor = (height - 1 - row) * 8
        line = ""
        for v in values:
            level = round(v / 100 * height * 8) - level_floor
            line += BLOCKS[max(0, min(8, level))]
        rows.append(line)
    return rows


def panel(title, lines, width, right="", footer="", rounded=False):
    tl, tr, bl, br = ("╭", "╮", "╰", "╯") if rounded else ("┌", "┐", "└", "┘")
    left = f"{tl}─ {title} "
    right_part = f" {right} ─{tr}" if right else f"─{tr}"
    top = left + "─" * (width - visible_len(left) - visible_len(right_part)) + right_part
    if footer:
        bottom_left = f"{bl}── {footer} "
        bottom = bottom_left + "─" * (width - visible_len(bottom_left) - 1) + br
    else:
        bottom = bl + "─" * (width - 2) + br
    body = ["│ " + pad(line, width - 4) + " │" for line in lines]
    return [top] + body + [bottom]


def side_by_side(*blocks):
    height = max(len(b) for b in blocks)
    widths = [visible_len(b[0]) for b in blocks]
    rows = []
    for i in range(height):
        parts = [b[i] if i < len(b) else " " * w for b, w in zip(blocks, widths)]
        rows.append(" ".join(parts))
    return rows

def wait_for_key(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if msvcrt.kbhit():
            return msvcrt.getwch().lower()
        time.sleep(0.05)
    return None

# --- Coded today (from Hackatime) ---

def hackatime_login():
    cfg = configparser.ConfigParser()
    cfg.read(os.path.expanduser("~/.wakatime.cfg"))
    try:
        url = cfg["settings"]["api_url"].rstrip("/")
        key = cfg["settings"]["api_key"]
    except KeyError:
        return None
    return url, "Basic " + base64.b64encode(key.encode()).decode()

def coded_today(login):
    if login is None:
        return None
    url, auth = login
    try:
        req = urllib.request.Request(f"{url}/users/current/statusbar/today", headers={"Authorization": auth})
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.load(r)["data"]["grand_total"]["total_seconds"]
    except (OSError, ValueError, KeyError):
        return None

def hm(seconds):
    hours, rest = divmod(int(seconds), 3600)
    return f"{hours}h {rest // 60}m"

def parse_args():
    p = argparse.ArgumentParser(description="Terminal dashboard for CPU, RAM, GPU, disk and network")
    p.add_argument("-i", "--interval", type=float, default=1.0, help="seconds between updates")
    p.add_argument("--disk", default=None, help="only show this drive (default: all drives)")
    p.add_argument("--goal", type=float, default=1.5, help="hours to code per day (default 1.5)")
    return p.parse_args()


def main():
    args = parse_args()
    os.system("")
    sys.stdout.write("\x1b[?25l\x1b[2J")

    HIST_MAX = 500
    cpu_hist = [0.0] * HIST_MAX
    ram_hist = [0.0] * HIST_MAX
    net_hist = [0.0] * HIST_MAX
    prev_idle, prev_total = cpu_times()
    adapters = gpu_adapters()
    query, counter = gpu_counter()
    net_query, net_recv, net_sent = net_counters()
    drives = [args.disk] if args.disk else fixed_drives()
    interval = args.interval
    paused = False
    login = hackatime_login()
    today = None
    next_fetch = 0.0

    try:
        while True:
            key = wait_for_key(interval)
            if key == "q":
                break
            if key == "+":
                interval = max(0.2, interval - 0.2)
            if key == "-":
                interval = min(5.0, interval + 0.2)
            if key == "p":
                paused = not paused
            if paused:
                sys.stdout.write("\x1b[H  \x1b[33mPAUSED\x1b[0m - press p to continue\x1b[K")
                sys.stdout.flush()
                continue
            
            idle, total = cpu_times()
            d_total = total - prev_total
            cpu = 100 * (1 - (idle - prev_idle) / d_total) if d_total else 0.0
            prev_idle, prev_total = idle, total

            ram, used, ram_total = ram_usage()

            cpu_hist = cpu_hist[1:] + [cpu]
            ram_hist = ram_hist[1:] + [ram]
            down, up = net_speed(net_query, net_recv, net_sent)
            net_hist = net_hist[1:] + [down]

            gpu_load = gpu_usage(query, counter) or 0.0
            gpu_temp = gpu_temperature(adapters)

            if time.monotonic() >= next_fetch:
                today = coded_today(login)
                next_fetch = time.monotonic() + 60

            gb = 1024 ** 3
            cols = shutil.get_terminal_size().columns
            total_w = max(60, min(cols - 1, 120))

            # --- Top: big clock + tall CPU graph ---
            now = time.localtime()
            clock = big_clock(time.strftime("%H:%M:%S", now))
            date = f"{DAYS[now.tm_wday]}, {MONTHS[now.tm_mon - 1]} {now.tm_mday}"
            left_col = [BOLD + row + RESET for row in clock] + [DIM + date + RESET]

            graph_w = total_w - 4 - 31 - 3
            cpu_graph = tall_graph(cpu_hist[-graph_w:], 3)
            header = f"CPU {'─' * (graph_w - 12)} {color(cpu)}{cpu:5.1f} %{RESET}"
            right_col = [header] + [color(cpu) + row + RESET for row in cpu_graph] + [DIM + "─" * graph_w + RESET, ""]

            top_lines = [pad(left, 31) + "   " + right for left, right in zip(left_col, right_col)]
            out = ["\x1b[H"]
            out += panel("TERMINAL-DASHBOARD", top_lines, total_w, right=f"q quit · +/- speed {interval:.1f}s · p pause", rounded=True)

            # --- Middle: RAM, GPU, NET ---
            w3 = (total_w - 2) // 3
            w_last = total_w - 2 - 2 * w3
            ram_box = panel("RAM", [color(ram) + bar(ram, w3 - 4) + RESET], w3,
                            right=f"{ram:.0f} %", footer=f"{used / gb:.1f} / {ram_total / gb:.1f} GB")
            gpu_temp_text = "" if gpu_temp is None else f" {gpu_temp:.0f}°C"
            gpu_box = panel("GPU", [color(gpu_load) + bar(gpu_load, w3 - 4) + RESET], w3,
                            right=f"{gpu_load:.0f} %{gpu_temp_text}")
            peak = max(max(net_hist[-(w_last - 4):]), 1)
            net_graph = sparkline([v / peak * 100 for v in net_hist[-(w_last - 4):]])
            net_box = panel("NET", [CYAN + net_graph + RESET], w_last,
                            right=f"↓ {fmt_speed(down).strip()}", footer=f"↑ {fmt_speed(up).strip()}")
            out += side_by_side(ram_box, gpu_box, net_box)

            # --- Bottom: DISK + SYSTEM ---
            sys_w = 30
            disk_w = total_w - sys_w - 1
            disk_bar_w = disk_w - 4 - 3 - 7 - 18
            disk_lines = []
            for d in drives:
                usage = shutil.disk_usage(d)
                pct = usage.used / usage.total * 100
                size = f"{usage.used / gb:.0f} / {usage.total / gb:.0f} GB"
                disk_lines.append(f"{d[:2]} {color(pct)}{bar(pct, disk_bar_w)}{RESET} {pct:4.0f} %  {size:>16}")
            sys_lines = [f"up {uptime_text()}", f"{len(drives)} drives found"]
            height = max(len(disk_lines), len(sys_lines))
            disk_lines += [""] * (height - len(disk_lines))
            sys_lines += [""] * (height - len(sys_lines))
            out += side_by_side(panel("DISK", disk_lines, disk_w), panel("SYSTEM", sys_lines, sys_w))

                        # --- Coded today ---
            if today is None:
                today_line = "--"
            else:
                goal = args.goal * 3600
                pct = min(today / goal * 100, 100)
                today_color = "\x1b[32m" if today >= goal else "\x1b[33m"
                today_line = f"{today_color}{bar(pct, total_w - 30)}{RESET}  {hm(today)} / {hm(goal)}"
            out += panel("CODE", [today_line], total_w, right="Hackatime")
            
            sys.stdout.write("\n".join(line + "\x1b[K" for line in out) + "\x1b[J")
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?25h\n")


if __name__ == "__main__":
    main()