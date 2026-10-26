import os
import sys

os.system("")

RESET = "\x1b[0m"

sys.stdout.write("\x1b[2J\x1b[H")
print("\x1b[1m TERMINAL-DASHBOARD" + RESET)
print("\x1b[32m CPU" + RESET)
print("\x1b[33m RAM" + RESET)
print("\x1b[31m TEMP")

BLOCKS = " ▁▂▃▄▅▆▇█"

def sparkline(values):
    return "".join(BLOCKS[round(v / 100 * 8)] for v in values)
