# term-dash

A live system monitor for the Windows terminal, written in Python with **no external libraries and no extra software** — only the standard library and what Windows already provides.

```
  TERMINAL-DASHBOARD   (Ctrl+C for at stoppe)

  CPU  ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  10.3 %
       ▁▁▂▁▁▃▅▂▁▁▁▂▁▁▁▁▂▃▂▁▁▁▂▁▁▁▁▂▃▂▁▁▂

  RAM  ███████████████████████████████████░░   86.1 %  (13.6 / 15.8 GB)
       ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇

  GPU  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0.2 %   43.0 °C

  DISK ██████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   26.1 %  (243 / 930 GB)
```

## Features

- **CPU** usage with a history graph
- **RAM** usage with a history graph
- **GPU** load and temperature (the same numbers Task Manager shows)
- **Disk** usage for any drive
- Colored bars: green below 50 %, yellow below 80 %, red above
- Bars and graphs resize to fit the terminal window
- Redraws in place without flicker, and restores the cursor on exit

## Requirements

- Windows 10 (version 2004 or newer) or Windows 11
- Python 3.8 or newer
- A terminal with Unicode and ANSI color support, such as Windows Terminal or the VS Code terminal

Nothing to install — no `pip install`, no background programs.

## Usage

```
python dashboard.py
```

Press **Ctrl+C** to quit.

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-i`, `--interval` | `1.0` | Seconds between updates |
| `--disk` | `C:\` | Which drive to show in the disk panel |

Example: update twice per second and show the D: drive:

```
python dashboard.py --interval 0.5 --disk D:\
```

## How it works

Everything is read straight from Windows through `ctypes`:

| Reading | Source |
| --- | --- |
| CPU | `GetSystemTimes` in `kernel32.dll`. Two readings apart: CPU % = 1 − idle time / total time. |
| RAM | `GlobalMemoryStatusEx` in `kernel32.dll` |
| GPU load | Windows performance counters (`GPU Engine … Utilization Percentage`) through `pdh.dll` |
| GPU temperature | The graphics driver's performance data through `D3DKMTQueryAdapterInfo` in `gdi32.dll` |
| Disk | `shutil.disk_usage` from the standard library |

The screen is drawn with ANSI escape codes for colors and cursor movement, and the block characters `▁▂▃▄▅▆▇█` for the graphs.

### Why no CPU temperature?

The CPU temperature lives in a special register inside the processor that can only be read from the Windows kernel. Windows does not pass it on to normal programs, so reading it would require a signed kernel driver (which is what tools like LibreHardwareMonitor install). GPU temperature works because Windows requires graphics drivers to report it.

## Roadmap

- [ ] One bar per CPU core
- [ ] Network traffic
- [ ] Boxes around each panel
