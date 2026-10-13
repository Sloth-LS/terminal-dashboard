# term-dash

A live system monitor for the Windows terminal, written in Python with **no external libraries** — only the standard library.

```
  TERMINAL-DASHBOARD   (Ctrl+C for at stoppe)

  CPU ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  17.1 %
      ▁▁▂▁▁▃▅▂▁▁▁▂▁▁▁▁▂▃▂▁

  RAM █████████████████████████████████░░░░░░░  84.6 %  (13.4 / 15.8 GB)
      ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇
```

## Features

- Live CPU and RAM usage, updated every second
- Colored bars: green below 50 %, yellow below 80 %, red above
- A 60-second history graph (sparkline) for each reading
- Redraws in place without flicker, and restores the cursor on exit

## Requirements

- Windows 10 or 11
- Python 3.8 or newer
- A terminal with Unicode and ANSI color support (Windows Terminal or the VS Code terminal)

## Run

```
python dashboard.py
```

Press **Ctrl+C** to quit.

## How it works

| Part | How |
| --- | --- |
| CPU | `GetSystemTimes` from `kernel32.dll` via `ctypes`. Two readings one second apart; CPU % = 1 − idle time / total time. |
| RAM | `GlobalMemoryStatusEx` from `kernel32.dll` via `ctypes`. |
| Drawing | ANSI escape codes for colors and cursor movement, and the block characters `▁▂▃▄▅▆▇█` for graphs. |
| Temperature and GPU | Read from [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor)'s local web server with `urllib` and `json`. |

## Temperature and GPU (work in progress)

Windows does not let normal programs read temperature sensors, so this part relies on LibreHardwareMonitor:

1. Download LibreHardwareMonitor and run it **as administrator**.
2. Turn on **Options → Remote Web Server → Run**.
3. The sensors are now available at `http://localhost:8085/data.json`.

The functions `sensors()` and `find_value()` already read this data, but the readings are not shown on screen yet.

## Roadmap

- [ ] Show CPU and GPU temperature
- [ ] Show GPU load and fan speeds
- [ ] One bar per CPU core
- [ ] Fit the width to the terminal window

## Files

| File | Description |
| --- | --- |
| `dashboard.py` | The dashboard |
| `dash.py` | Practice file from the first steps |
