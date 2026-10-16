# term-dash

A live system monitor for the Windows terminal, written in Python with **no external libraries and no extra software** — only the standard library and what Windows already provides.

```
  TERMINAL-DASHBOARD   01:49:17   (Ctrl+C to stop)

┌─ CPU ──────────────────────────────────────────────────────────────┐
│ ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  11.0 %                     │
│ ▁▁▂▁▁▃▅▂▁▁▁▂▁▁▁▁▂▃▂▁▁▁▂▁▁▁▁▂▃▂▁                             │       
└────────────────────────────────────────────────────────────────────┘
┌─ RAM ──────────────────────────────────────────────────────────────┐
│ ████████████████████████████████░░░░░░  84.9 %  (13.4 / 15.8 GB)   │
│ ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇                             │                             
└────────────────────────────────────────────────────────────────────┘
┌─ GPU ──────────────────────────────────────────────────────────────┐
│ █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   1.8 %   44.0 °C           │
└────────────────────────────────────────────────────────────────────┘
┌─ DISK ─────────────────────────────────────────────────────────────┐
│ ███████████░░░░░░░░░░░░░░░░░░░░░░░░░░░  27.7 %  (258 / 930 GB)     │
└────────────────────────────────────────────────────────────────────┘
┌─ NET ──────────────────────────────────────────────────────────────┐
│ ↓    0.7 KB/s   ↑    0.5 KB/s                                      │
│ ▁▁▁▁▂▁▁▁▁▁▁▁▃▇█▅▂▁▁▁▁▁▁▁▁▁▁▁▁▁▁▂▁▁▁▁▁▂                     │        
└────────────────────────────────────────────────────────────────────┘
┌─ UPTIME ───────────────────────────────────────────────────────────┐
│ 0 d 6 t 26 min                                                     │
└────────────────────────────────────────────────────────────────────┘
```

## Features

- **CPU** usage with a history graph
- **RAM** usage with a history graph
- **GPU** load and temperature (the same numbers Task Manager shows)
- **Disk** usage for any drive
- **Network** download and upload speed with a history graph
- **Uptime** — how long the PC has been on
- A clock in the title
- Each panel drawn in its own box
- Colored bars: green below 50 %, yellow below 80 %, red above
- Bars, graphs and boxes resize to fit the terminal window
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
| Network | Windows performance counters (`Network Interface … Bytes Received/sec` and `Bytes Sent/sec`) through `pdh.dll`, summed over all network adapters |
| Uptime | `GetTickCount64` in `kernel32.dll` |
| Disk | `shutil.disk_usage` from the standard library |

The screen is drawn with ANSI escape codes for colors and cursor movement, box-drawing characters (`┌ ─ ┐ │ └ ┘`) for the panels, and the block characters `▁▂▃▄▅▆▇█` for the graphs.

### Reading the network panel

The network panel shows how much the connection is being **used right now**, not how fast it can go. When nothing is downloading it shows a few KB/s of background traffic. Speeds are in bytes (KB/s and MB/s, like Steam and Windows use); internet plans are sold in bits, so a 100 Mbit/s connection tops out around 12 MB/s.

The network graph scales to the highest speed in its history, since network traffic has no fixed 100 % maximum.

### Why no CPU temperature?

The CPU temperature lives in a special register inside the processor that can only be read from the Windows kernel. Windows does not pass it on to normal programs, so reading it would require a signed kernel driver (which is what tools like LibreHardwareMonitor install). GPU temperature works because Windows requires graphics drivers to report it.

## Roadmap

- [ ] Disk usage for every drive
- [ ] Top 5 programs by RAM usage
- [ ] One bar per CPU core
- [ ] Save settings in a `settings.json` file
