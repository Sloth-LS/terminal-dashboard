import argparse
import ctypes
import os
import re
import shutil
import sys
import time
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
    return f"{days} d {hours} t {minutes} min"



ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def box(title, lines, inner):
    top = "┌─ " + title + " " + "─" * (inner - len(title) - 1) + "┐"
    body = []
    for line in lines:
        pad = inner - len(ANSI.sub("", line))
        body.append("│ " + line + " " * pad + " │")
    bottom = "└" + "─" * (inner + 2) + "┘"
    return [top] + body + [bottom]


def parse_args():
    p = argparse.ArgumentParser(description="Terminal-dashboard til CPU, RAM, GPU og disk")
    p.add_argument("-i", "--interval", type=float, default=1.0, help="sekunder mellem opdateringer")
    p.add_argument("--disk", default="C:\\", help="drev der vises i disk-panelet")
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
            down, up = net_speed(net_query, net_recv, net_sent)
            net_hist = net_hist[1:] + [down]


            gpu_load = gpu_usage(query, counter)
            gpu_temp = gpu_temperature(adapters)

            disk = shutil.disk_usage(args.disk)
            disk_pct = disk.used / disk.total * 100

            cols = shutil.get_terminal_size().columns
            width = max(10, min(cols - 40, 100))
            hist_len = width

            gb = 1024 ** 3
            inner = width + 28
            if gpu_load is None:
                gpu_line = "n/a"
            else:
                gpu_line = f"{color(gpu_load)}{bar(gpu_load, width)}{RESET} {gpu_load:5.1f} %  {fmt_temp(gpu_temp)}"

            out = [f"\x1b[H\x1b[1m  TERMINAL-DASHBOARD\x1b[0m   {time.strftime('%H:%M:%S')}   (Ctrl+C to stop)", ""]
            out += box("CPU", [
                f"{color(cpu)}{bar(cpu, width)}{RESET} {cpu:5.1f} %",
                f"{color(cpu)}{sparkline(cpu_hist[-hist_len:])}{RESET}",
            ], inner)
            out += box("RAM", [
                f"{color(ram)}{bar(ram, width)}{RESET} {ram:5.1f} %  ({used / gb:.1f} / {ram_total / gb:.1f} GB)",
                f"{color(ram)}{sparkline(ram_hist[-hist_len:])}{RESET}",
            ], inner)
            out += box("GPU", [gpu_line], inner)
            out += box("DISK", [
                f"{color(disk_pct)}{bar(disk_pct, width)}{RESET} {disk_pct:5.1f} %  ({disk.used / gb:.0f} / {disk.total / gb:.0f} GB)",
            ], inner)
            peak = max(max(net_hist[-hist_len:]), 1)
            net_graph = sparkline([v / peak * 100 for v in net_hist[-hist_len:]])
            out += box("NET", [
                f"↓ {fmt_speed(down)}   ↑ {fmt_speed(up)}",
                f"\x1b[36m{net_graph}{RESET}",
            ], inner)
            out += box("UPTIME", [uptime_text()], inner)
            
            
            sys.stdout.write("\n".join(line + "\x1b[K" for line in out) + "\x1b[J")
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?25h\n")

if __name__ == "__main__":
    main()
