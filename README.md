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

Every `--interval` seconds (default 20), fetches a random image from
`libretro-artwork-api`'s `/random` endpoint whose own pixel shape
matches the screen's `--orientation` (a wide image discarded on a
portrait screen, and vice versa - up to `MAX_ORIENTATION_RETRIES` tries;
box art skews heavily portrait, so a landscape screen restricted to a
narrow `--type` may struggle to find a match), fits it to the screen
(letterboxed on black, preserving aspect ratio), and pushes it to the
display. Skips an immediate repeat of the same image. A fetch or
display failure just logs and retries next tick - never crashes the
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
--type TYPE         boxart|snap|title|logo, a comma-list ("boxart,snap") to pick
                    randomly among those, or "random" for any of the four (default: boxart)
--orientation       landscape|portrait|reverse_landscape|reverse_portrait (default: landscape)
--allow-square-images / --no-allow-square-images
                    whether a square-ish image (long/short side ratio under
                    SQUARE_ISH_RATIO, 1.1 by default - not just exactly equal
                    dimensions) counts as matching either orientation, or gets
                    rejected/retried like any other shape mismatch (default: allow)
--port PORT          serial port (default: AUTO)
--brightness 0-100    (default: 50)
--fetch-timeout SECONDS  HTTP timeout (default: 8)
```

## Box art shape by system

Measured directly (2026-08-28) rather than guessed from memory of
physical packaging conventions, which vary by region/scan and turned
out to be wrong in at least one case (Genesis reads as 99.9% portrait
here, not landscape as commonly assumed). Method: read every PNG's
width/height from its header (no decode needed) for each system's
`Named_Boxarts/`, bucket each as landscape (`ratio > 1.1`), portrait
(`ratio < 1/1.1`), or square-ish, same threshold `random_art_display.py`
itself uses. "Dominant" below means whichever bucket has the plurality.

| System | alias | n | landscape | portrait | square | dominant |
| --- | --- | --- | --- | --- | --- | --- |
| Nintendo 64DD | *(none - see below)* | 28 | 27 | 1 | 0 | **landscape (96%)** |
| Nintendo 64 | `n64` | 1115 | 808 | 307 | 0 | **landscape (72%)** |
| SNES | `snes` | 3701 | 2156 | 1542 | 3 | **landscape (58%)** |
| Sega CD/Mega-CD | `megacd` | 609 | 175 | 297 | 137 | portrait (weak plurality, genuinely mixed) |
| Game Boy Advance | `gba` | 5958 | 1479 | 2572 | 1907 | portrait (weak plurality, genuinely mixed) |
| 3DO | `3do` | 652 | 100 | 360 | 192 | portrait |
| NES | `nes` | 13438 | 3307 | 10049 | 82 | portrait |
| Neo Geo | `neogeo` | 257 | 18 | 237 | 2 | portrait |
| Sega 32X | `s32x` | 208 | 8 | 200 | 0 | portrait |
| Atari Lynx | `atarilynx` | 97 | 1 | 96 | 0 | portrait |
| WonderSwan | `wonderswan` | 299 | 4 | 295 | 0 | portrait |
| WonderSwan Color | `wonderswancolor` | 239 | 2 | 237 | 0 | portrait |
| Game Gear | `gg` | 605 | 3 | 602 | 0 | portrait |
| Master System | `mastersystem` | 560 | 2 | 558 | 0 | portrait |
| Genesis/Mega Drive | `genesis` | 2354 | 2 | 2352 | 0 | portrait |
| Sega SG-1000 | *(none - see below)* | 141 | 0 | 141 | 0 | portrait (100%) |
| Saturn | `saturn` | 2296 | 85 | 991 | 1220 | square |
| PlayStation | `psx` | 9347 | 530 | 55 | 8762 | square |
| Game Boy Color | `gbc` | 1522 | 74 | 463 | 985 | square |
| Game Boy | `gb` | 1645 | 32 | 597 | 1016 | square |
| Family Computer Disk System | `fds` | 396 | 4 | 94 | 298 | square |
| PC Engine/TurboGrafx-16 | `tgfx16` | 479 | 26 | 9 | 444 | square |
| PC Engine CD | *(none - see below)* | 946 | 49 | 20 | 877 | square |
| Neo Geo CD | *(none - see below)* | 216 | 0 | 1 | 215 | square |
| MAME (arcade) | `arcade` | 6068 | 319 | 5722 | 27 | portrait, but flyers/mixed - not comparable to real console box art |

**`Nintendo_-_Nintendo_64DD`, `Sega_-_SG-1000`, `NEC_-_PC_Engine_CD_-_TurboGrafx-CD`,
and `SNK_-_Neo_Geo_CD` have no `SYSTEM_MAP` alias** (see `libretro-artwork-api`'s
own comment on why - they have no MiSTer `core_raw` of their own to route
through, so an alias was deliberately never guessed at) - not usable in
`--system`/`--exclude-system` today even though they're indexed. N64DD in
particular is the single strongest landscape system measured (96%) but
can't currently be selected.

**Landscape config** (`--system n64,snes`): both are genuinely
landscape-majority, not just landscape-present - combined pool is 62%
landscape, comfortably within `MAX_ORIENTATION_RETRIES`.

## Currently deployed

Raspberry Pi 3 (OSMC), `/home/osmc/random-art-display/`, running as the
`random-art-display` systemd service. Logs:
`sudo journalctl -u random-art-display -f`.

## License

GPL-3.0-or-later - see `LICENSE`. `turing_lcd/` is vendored from
[mathoudebine/turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python)
(same license); see that project for full attribution.
