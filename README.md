# random-art-display

A random game box art slideshow for a USB-C "Turing" style smart screen.
Standalone - **not MiSTer-specific**, despite reusing code from
[mister_turing_client](https://gitea.ninjas.asia/kadafi/mister_turing_client).
Currently running on a Raspberry Pi (OSMC) with the display, unrelated to
any MiSTer setup.

## Requires [libretro-artwork-api](https://gitea.ninjas.asia/kadafi/libretro-artwork-api)

This client has no artwork of its own and does no matching/lookup logic -
it just asks a running `libretro-artwork-api` instance for
`GET /random` and displays whatever comes back. That sibling project is
what actually indexes the libretro-thumbnails data and serves images;
this repo is only the display-side loop. Point `--server` (required, no
default - e.g. `http://192.168.1.100:8478`) at an instance running the
`/random` endpoint - **not the older releases of that project**,
`/random` was added specifically to support this client (see that
repo's README API section).

## What it does

Every `--interval` seconds (default 20), fetches one random image from
`libretro-artwork-api`'s `/random` endpoint, fits it to the screen
(letterboxed on black, preserving aspect ratio - box art proportions
vary a lot, from tall SNES covers to wide arcade marquees), and pushes
it to the display. Skips an immediate repeat of the same image. A fetch
or display failure just logs and retries next tick - never crashes the
loop.

## Hardware / display driver

Reuses `turing_lcd/` verbatim from `mister_turing_client` - same
vendored, GPL-3.0-or-later library
([mathoudebine/turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python)),
same display hardware (a CH340-based USB-C "Turing"/UsbMonitor style
screen, shows up as `/dev/ttyACM0`). Includes the `write_timeout` fix
from that project - see its own `TROUBLESHOOTING.md` for why that
matters (a bad serial link can otherwise freeze the whole process
indefinitely with no error anywhere).

## Setup

Dependencies (Debian/Raspberry Pi OS/OSMC - no `pip` needed):

```
sudo apt-get install python3-serial python3-numpy python3-pil
```

(`python3-pil` may already be present.) Copy this whole directory to
the target machine, then either run it directly:

```
python3 random_art_display.py --server http://192.168.1.100:8478 --interval 20
```

or install it as a systemd service (recommended - survives reboots and
restarts on failure):

```
sudo cp random-art-display.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now random-art-display
```

Edit the `ExecStart` line in `random-art-display.service` first -
`--server` has no default, it needs your actual `libretro-artwork-api`
host/port - and to set a different `--interval`/`--system`/`--type` if
you want one.

## Options

```
--server URL       libretro-artwork-api base URL, e.g. http://192.168.1.100:8478 (required)
--interval SECONDS seconds between images (default: 20)
--system NAME       restrict to one SYSTEM_MAP alias (default: any indexed system)
--type TYPE         boxart|snap|title|logo (default: boxart)
--port PORT          serial port (default: AUTO)
--brightness 0-100    (default: 50)
--fetch-timeout SECONDS  HTTP timeout (default: 8)
```

## Currently deployed

Raspberry Pi 3 (OSMC), `/home/osmc/random-art-display/`, running as the
`random-art-display` systemd service. Logs:
`sudo journalctl -u random-art-display -f`.

## License

GPL-3.0-or-later - see `LICENSE`. `turing_lcd/` is vendored from
[mathoudebine/turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python)
(same license); see that project for full attribution.
