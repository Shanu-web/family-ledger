#!/usr/bin/env bash
# Builds a Netlify drag-and-drop zip with only the guest-facing pages.
# The site root (index.html) is the envelope-and-card experience. Left out: planner/ (money and
# counts), hamper.html (tiers and budget), the internal landing page, tools/, README.
set -euo pipefail
cd "$(dirname "$0")/.."
out="$(realpath -m "${1:-../shanu-sonali-site.zip}")"
tmp="$(mktemp -d)"
node tools/make_ics.js >/dev/null
cp -r assets wedding.config.js index.html invitation.html guest.html magazine.html shanu-sonali.ics _headers "$tmp/"
rm -f "$tmp"/assets/qr-*.png "$tmp"/assets/qr-*.svg
rm -f "$out"; (cd "$tmp" && zip -qr "$out" .)
rm -rf "$tmp"
echo "built $out"; unzip -l "$out" | tail -1
