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
