#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""random_art_display.py - pulls a random game box art image from a
self-hosted libretro-artwork-api instance (see the sibling
../libretro-artwork-api project) and shows it on a USB-C "Turing" style
smart screen, rotating to a new random image every --interval seconds.

Standalone - not MiSTer-specific. Reuses the same vendored turing_lcd/
display driver mister_turing_client uses (same hardware, same GPL-3.0-or-
later vendored library), just with a much simpler poll loop: no game
identity, no core state, just "show something, wait, show something else".

Run:
    python3 random_art_display.py --server http://192.168.1.100:8478
"""

import argparse
import io
import time
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image

from turing_lcd.lcd_comm import Orientation
from turing_lcd.lcd_comm_rev_a import LcdCommRevA
from turing_lcd.log import logger

BG = (0, 0, 0)


def fetch_random(server: str, system: str, media_type: str, timeout: float):
    """Returns (PIL.Image, label) or (None, reason) on failure. label is
    "type: system/filename" from the response headers - only used for
    logging and same-image dedup, the server doesn't send a game title.
    The type prefix matters once --type is a list or "random" - the
    caller otherwise has no way to tell which one it got."""
    params = {"type": media_type}
    if system:
        params["system"] = system
    url = f"{server.rstrip('/')}/random?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "random-art-display"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            filename = resp.headers.get("X-Filename", "")
            repo = resp.headers.get("X-System", "")
            picked_type = resp.headers.get("X-Type", media_type)
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)

    try:
        image = Image.open(io.BytesIO(body)).convert("RGB")
    except Exception as e:
        return None, f"bad image data: {e}"

    return image, f"{picked_type}: {repo}/{urllib.parse.unquote(filename)}"


def render_fit(image: Image.Image, width: int, height: int) -> Image.Image:
    """Box art aspect ratios vary a lot (tall SNES covers, wide arcade
    marquees, ...) - fit the whole image within the screen, preserving
    aspect ratio, letterboxed on black, rather than cropping any of it
    away or stretching it out of shape."""
    frame = Image.new("RGB", (width, height), BG)
    fitted = image.copy()
    fitted.thumbnail((width, height), Image.LANCZOS)
    x = (width - fitted.width) // 2
    y = (height - fitted.height) // 2
    frame.paste(fitted, (x, y))
    return frame


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--server", required=True,
                     help="libretro-artwork-api base URL, e.g. http://192.168.1.100:8478 "
                          "(required - no default, this varies per network)")
    ap.add_argument("--interval", type=float, default=20.0,
                     help="seconds between images (default: %(default)s)")
    ap.add_argument("--system", default="",
                     help="restrict to one SYSTEM_MAP alias (default: any indexed system)")
    ap.add_argument("--type", default="boxart",
                     help="boxart|snap|title|logo, a comma-separated list to pick "
                          "randomly among ('boxart,snap'), or 'random' for any of the "
                          "four (default: %(default)s) - passed straight through to "
                          "the server, which validates it")
    ap.add_argument("--orientation", default="landscape",
                     choices=["landscape", "portrait", "reverse_landscape", "reverse_portrait"],
                     help="physical mount orientation (default: %(default)s)")
    ap.add_argument("--port", default="AUTO", help="serial port (default: auto-detect)")
    ap.add_argument("--brightness", type=int, default=50, help="0-100 (default: %(default)s)")
    ap.add_argument("--fetch-timeout", type=float, default=8.0,
                     help="HTTP timeout in seconds (default: %(default)s)")
    args = ap.parse_args()

    comm = LcdCommRevA(com_port=args.port, display_width=320, display_height=480)
    comm.InitializeComm()
    comm.SetBrightness(args.brightness)
    comm.Clear()
    comm.SetOrientation(Orientation[args.orientation.upper()])
    width, height = comm.get_width(), comm.get_height()
    logger.info("Display ready: %dx%d", width, height)

    last_label = None
    try:
        while True:
            image, label = fetch_random(args.server, args.system, args.type, args.fetch_timeout)
            if image is None:
                logger.warning("Fetch failed (%s), retrying in %.0fs", label, args.interval)
            elif label == last_label:
                # The index is large enough in practice that an immediate
                # repeat is rare - when it happens, just skip this tick
                # rather than show the same image twice in a row.
                logger.debug("Same image again (%s), skipping this tick", label)
            else:
                frame = render_fit(image, width, height)
                try:
                    comm.DisplayPILImage(frame)
                    last_label = label
                    logger.info("Showing %s", label)
                except Exception as e:
                    # Mirrors mister_turing_client's own reasoning: a
                    # single bad push shouldn't take the whole loop down,
                    # just log and try again next tick.
                    logger.error("Display update failed: %s", e)

            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        comm.closeSerial()


if __name__ == "__main__":
    main()
