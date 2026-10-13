# Terminal dashboard: CPU, RAM, GPU and temperature live in the terminal.
# Python standard library only. Follow the guide step by step and fill in each TODO.
#
# Run:  python D:\term-dash\dash.py
#
# The template runs right away. The functions return 0 for now,
# so you can watch the dashboard improve as you fill them in.

import ctypes
import os
import sys
import time
from ctypes import wintypes

# --- Step 1: ANSI codes -------------------------------------------------------

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"


def colored(text, code):
    # TODO step 1: return the text with the color code in front and RESET after
    return text


# --- Step 2: bars and graphs --------------------------------------------------

BLOCKS = " ▁▂▃▄▅▆▇█"


def bar(pct, width=40):
    # TODO step 2: build a bar of "█" (filled) and "░" (empty), width chars total
    return "░" * width


def sparkline(values):
    # TODO step 2: turn each number (0-100) into a character from BLOCKS
    return ""


# --- Step 3: RAM --------------------------------------------------------------

kernel32 = ctypes.windll.kernel32


class MEMORYSTATUSEX(ctypes.Structure):
    # TODO step 3: write the 9 fields (see the guide or Microsoft's documentation)
    _fields_ = []


def ram_usage():
    # TODO step 3: call kernel32.GlobalMemoryStatusEx and return
    #              (percent, used bytes, total bytes)
    return 0.0, 0, 1


# --- Step 4: CPU --------------------------------------------------------------

class FILETIME(ctypes.Structure):
    # TODO step 4: two fields, "low" and "high", both wintypes.DWORD
    _fields_ = []


def to_int(ft):
    # TODO step 4: combine high and low into one 64-bit number
    return 0


def cpu_times():
    # TODO step 4: call kernel32.GetSystemTimes and return (idle, total)
    #              remember: total = kernel + user
    return 0, 0


# --- Step 6: colors by threshold ----------------------------------------------

def color(pct):
    # TODO step 6: green below 50, yellow below 80, otherwise red
    return ""


# --- Step 7: temperature and GPU via LibreHardwareMonitor ---------------------

URL = "http://localhost:8085/data.json"


def walk(node, path, out):
    # TODO step 7: walk the tree recursively and collect (path, value) in out
    pass


def sensors():
    # TODO step 7: fetch URL with urllib.request, parse the JSON and call walk
    return []


def find_value(data, ending):
    # TODO step 7: find the sensor whose path ends with ending, return the number
    return None


# --- Step 5: main loop --------------------------------------------------------

def main():
    os.system("")  # enables ANSI codes in the Windows console
    sys.stdout.write("\x1b[?25l\x1b[2J")  # hide cursor, clear screen once

    cpu_hist = [0.0] * 60
    ram_hist = [0.0] * 60
    prev_idle, prev_total = cpu_times()

    try:
        while True:
            time.sleep(1)

            # TODO step 5: calculate cpu from the difference since the last reading
            idle, total = cpu_times()
            cpu = 0.0
            prev_idle, prev_total = idle, total

            ram, used, ram_total = ram_usage()

            # TODO step 6: update cpu_hist and ram_hist (drop the oldest value)

            # TODO step 7: data = sensors() and look up GPU and temperatures

            gb = 1024 ** 3
            out = [
                "\x1b[H" + colored("  TERMINAL DASHBOARD", BOLD) + "   (Ctrl+C to quit)",
                "",
                f"  CPU {bar(cpu)} {cpu:5.1f} %",
                f"      {sparkline(cpu_hist)}",
                "",
                f"  RAM {bar(ram)} {ram:5.1f} %  ({used / gb:.1f} / {ram_total / gb:.1f} GB)",
                f"      {sparkline(ram_hist)}",
            ]
            sys.stdout.write("\n".join(line + "\x1b[K" for line in out))
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?25h\n")  # show the cursor again


if __name__ == "__main__":
    main()
