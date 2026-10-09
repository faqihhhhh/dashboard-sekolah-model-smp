#!/usr/bin/env bash
# Mengunduh Tailwind CSS CLI mandiri (tanpa Node.js) ke bin/tailwindcss.
set -euo pipefail
cd "$(dirname "$0")/.."

TAILWIND_VERSION="v4.3.3"

case "$(uname -m)" in
  x86_64)  ARCH="x64" ;;
  aarch64) ARCH="arm64" ;;
  *) echo "Arsitektur tidak didukung: $(uname -m)" >&2; exit 1 ;;
esac

mkdir -p bin
curl -fsSL -o bin/tailwindcss \
  "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-${ARCH}"
chmod +x bin/tailwindcss
./bin/tailwindcss --help | head -1
