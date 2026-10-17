# term-dash

A live system monitor for the Windows terminal, written in Python with **no external libraries and no extra software** — only the standard library and what Windows already provides.

```
╭─ TERMINAL-DASHBOARD ─────────────────────────────────────── Ctrl+C to stop ─╮
│  █  ███     ███ ███     █ █ ███   CPU ─────────────────────────────  12.8 % │
│ ██    █  ▀    █   █  ▀  █ █ █ █                                             │
│  █    █     ███ ███     ███ ███            ▂       ▄                        │
│  █    █  ▄  █     █  ▄    █ █ █   ▁▂▄█▄▂▁▁▂▃▂▁▁▁▂▄▅▃▂▁▁▃█▆▄▂▁▂▄▆█▅▃▂▁▃▃▄    │
│ ███   █     ███ ███       █ ███   ───────────────────────────────────────── │
│ Saturday, October 17                                                        │
╰─────────────────────────────────────────────────────────────────────────────╯
┌─ RAM ────────── 71 % ─┐ ┌─ GPU ────── 2 % 46°C ─┐ ┌─ NET ─── ↓ 337.0 KB/s ─┐
│ ███████████████░░░░░░ │ │ █░░░░░░░░░░░░░░░░░░░░ │ │ ▁▁▃▇█▅▂▁▁▁▁▂▁▁▁▁▁▂▁▁▁ │
└── 11.2 / 15.8 GB ─────┘ └───────────────────────┘ └── ↑ 15.1 KB/s ─────────┘
┌─ DISK ───────────────────────────────────────┐ ┌─ SYSTEM ───────────────────┐
│ C: ████░░░░░░░░░░░░   26 %      244 / 930 GB │ │ up 0 d 2 h 27 min          │
│ D: ██░░░░░░░░░░░░░░   12 %     221 / 1863 GB │ │ 2 drives found             │
└──────────────────────────────────────────────┘ └────────────────────────────┘
```

## Features

- **Big clock** with the date
- **CPU** usage with a 3-line-tall history graph
- **RAM** usage
- **GPU** load and temperature (the same numbers Task Manager shows)
- **Network** download and upload speed with a history graph
- **Disk** usage for **every drive**, found automatically
- **Uptime** — how long the PC has been on
- Grid layout with panels side by side and rounded corners on the top panel
- Colored bars: green below 50 %, yellow below 80 %, red above
- Everything resizes to fit the terminal window
- Redraws in place without flicker, and restores the cursor on exit

## Requirements

- Windows 10 (version 2004 or newer) or Windows 11
- Python 3.8 or newer
- A terminal with Unicode and ANSI color support, such as Windows Terminal or the VS Code terminal
- A window of at least 80 × 18 characters

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
| `--disk` | all drives | Show only this drive, e.g. `--disk D:\` |

## How it works

Everything is read straight from Windows through `ctypes`:

| Reading | Source |
| --- | --- |
| CPU | `GetSystemTimes` in `kernel32.dll`. Two readings apart: CPU % = 1 − idle time / total time. |
| RAM | `GlobalMemoryStatusEx` in `kernel32.dll` |
| GPU load | Windows performance counters (`GPU Engine … Utilization Percentage`) through `pdh.dll` |
| GPU temperature | The graphics driver's performance data through `D3DKMTQueryAdapterInfo` in `gdi32.dll` |
| Network | Windows performance counters (`Network Interface … Bytes Received/sec` and `Bytes Sent/sec`) through `pdh.dll` |
| Drives | `GetLogicalDrives` and `GetDriveTypeW` in `kernel32.dll` find every fixed disk |
| Disk usage | `shutil.disk_usage` from the standard library |
| Uptime | `GetTickCount64` in `kernel32.dll` |

### Drawing

| Part | How |
| --- | --- |
| Big clock | A small "font" where each digit is 5 rows of `█` characters |
| Tall graph | Each column is filled from the bottom up across 3 rows using `▁▂▃▄▅▆▇█` |
| Panels | `panel()` draws a box with a title and values in the border |
| Grid | `side_by_side()` joins panels line by line |
| Colors | ANSI escape codes, which are stripped when measuring text width so the borders line up |

### Reading the network panel

The network panel shows how much the connection is being **used right now**, not how fast it can go. When nothing is downloading it shows a few KB/s of background traffic. Speeds are in bytes (KB/s and MB/s); internet plans are sold in bits, so a 100 Mbit/s connection tops out around 12 MB/s.

### Why no CPU temperature?

The CPU temperature lives in a register inside the processor that can only be read from the Windows kernel. Windows does not pass it on to normal programs, so reading it would require a signed kernel driver. GPU temperature works because Windows requires graphics drivers to report it.

## Roadmap

- [ ] Keyboard controls (`q` to quit, `+`/`-` to change speed)
- [ ] Top 5 programs by RAM usage
- [ ] One bar per CPU core
- [ ] Save settings in a `settings.json` file
