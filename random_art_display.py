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


MAX_ORIENTATION_RETRIES = 25


SQUARE_ISH_RATIO = 1.1  # long side / short side below this counts as "square" too


def shape_matches(image: Image.Image, want_landscape: bool, allow_square: bool = True) -> bool:
    """Compares the image's own pixel shape (not the screen's physical
    mount) against what's wanted - a wide image on a portrait screen (or
    vice versa) still displays fine via render_fit()'s letterboxing, but
    looks small and wastes most of the screen. "Square" means square-ish
    (within SQUARE_ISH_RATIO), not just exactly equal dimensions - a real
    512x508 PC Engine CD cover (ratio 1.008, a jewel-case-style cover)
    read as square to the eye but passed an exact-equality check as
    "landscape" by one pixel. A square-ish image matches either
    orientation by default (there's no wrong choice for it), unless
    allow_square is False - then it's rejected like any other mismatch,
    same retry-and-skip handling."""
    long_side, short_side = max(image.width, image.height), min(image.width, image.height)
    if short_side == 0 or long_side / short_side < SQUARE_ISH_RATIO:
        return allow_square
    return (image.width > image.height) == want_landscape


def fetch_matching(server: str, system: str, media_type: str, timeout: float,
                    want_landscape: bool, allow_square: bool = True):
    """Like fetch_random(), but discards a shape-mismatched image and
    tries again, up to MAX_ORIENTATION_RETRIES times. Box art in
    particular skews heavily portrait (mimics a physical cover), so a
    landscape screen restricted to a narrow --type could plausibly
    exhaust every retry - that's reported the same way a plain fetch
    failure is, not treated as an error, since it isn't one: nothing
    matching was available yet, not that something went wrong."""
    for attempt in range(1, MAX_ORIENTATION_RETRIES + 1):
        image, label = fetch_random(server, system, media_type, timeout)
        if image is None:
            return None, label
        if shape_matches(image, want_landscape, allow_square):
            return image, label
        logger.debug("Wrong shape for this orientation (%s), retrying (%d/%d)",
                     label, attempt, MAX_ORIENTATION_RETRIES)
    return None, f"no {'landscape' if want_landscape else 'portrait'}-shaped image found " \
                 f"in {MAX_ORIENTATION_RETRIES} tries"


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
    ap.add_argument("--allow-square-images", action=argparse.BooleanOptionalAction, default=True,
                     help="whether an exactly-square image counts as matching either "
                          "orientation, or gets rejected/retried like any other shape "
                          "mismatch (default: %(default)s)")
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

    want_landscape = args.orientation in ("landscape", "reverse_landscape")

    last_label = None
    try:
        while True:
            image, label = fetch_matching(args.server, args.system, args.type, args.fetch_timeout,
                                          want_landscape, args.allow_square_images)
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
