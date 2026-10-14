#!/usr/bin/env bash
# Mengunduh library JavaScript ke static/vendor/ (disimpan lokal, tanpa CDN).
# Jalankan ulang hanya saat ingin menaikkan versi; hasilnya di-commit ke git.
set -euo pipefail
cd "$(dirname "$0")/.."

HTMX_VERSION="2.0.11"
ALPINE_VERSION="3.17.4"

mkdir -p static/vendor

# fetch_npm <paket> <versi> <berkas-dalam-paket> <tujuan>
fetch_npm() {
  curl -fsSL "https://registry.npmjs.org/$1/-/$1-$2.tgz" \
    | tar -xzO "package/$3" > "$4"
  echo "ok: $4 ($(wc -c < "$4") bytes)"
}

fetch_npm htmx.org "$HTMX_VERSION" dist/htmx.min.js static/vendor/htmx.min.js
fetch_npm alpinejs "$ALPINE_VERSION" dist/cdn.min.js static/vendor/alpine.min.js

# Font Plus Jakarta Sans (disimpan lokal, tanpa CDN)
mkdir -p static/fonts
FONT_VERSION="5.0.21"
curl -fsSL "https://registry.npmjs.org/@fontsource/plus-jakarta-sans/-/plus-jakarta-sans-${FONT_VERSION}.tgz" \
  | tar -xz -C static/fonts/ --strip-components=2 \
    "package/files/plus-jakarta-sans-latin-400-normal.woff2" \
    "package/files/plus-jakarta-sans-latin-500-normal.woff2" \
    "package/files/plus-jakarta-sans-latin-600-normal.woff2" \
    "package/files/plus-jakarta-sans-latin-700-normal.woff2" \
    "package/files/plus-jakarta-sans-latin-800-normal.woff2"
echo "ok: fonts static/fonts/ (Plus Jakarta Sans woff2)"
