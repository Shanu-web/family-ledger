#!/usr/bin/env python3
"""Export print-ready QR codes for the guest page (and the directions link).

    pip install segno
    python3 wedding/tools/make_qr.py            # writes wedding/assets/qr-guest.svg/.png and qr-directions.svg

The web pages render their own QR live from wedding.config.js; this script is for
the printer, who wants a vector file. Colours match the design tokens.
"""
import json, re, pathlib, subprocess, sys
try:
    import segno
except ImportError:
    sys.exit("pip install segno")

ROOT = pathlib.Path(__file__).resolve().parents[1]
cfg = (ROOT / "wedding.config.js").read_text(encoding="utf-8")
guest = re.search(r'guestUrl:\s*"([^"]+)"', cfg).group(1)
maps = re.search(r'mapsQuery:\s*"([^"]+)"', cfg).group(1)
directions = "https://www.google.com/maps/dir/?api=1&destination=" + __import__("urllib.parse").parse.quote(maps)

out = ROOT / "assets"
for name, url in (("qr-guest", guest), ("qr-directions", directions)):
    qr = segno.make(url, error="h")
    qr.save(out / f"{name}.svg", scale=10, dark="#1C1A18", light="#FFFFFF", border=2)
    qr.save(out / f"{name}.png", scale=20, dark="#1C1A18", light="#FFFFFF", border=2)
    print(f"{name}: {url}")
