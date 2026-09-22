#!/usr/bin/env bash
# Linux container entrypoint:
#   1) virtual display (Xvfb) so Chrome can run on a headless VM
#   2) real Google Chrome with remote debugging (CDP)
#   3) visa monitor attached to that Chrome
set -euo pipefail

export DISPLAY="${DISPLAY:-:99}"
export BROWSER_MODE="${BROWSER_MODE:-cdp}"
export HEADLESS="${HEADLESS:-false}"
export CDP_PORT="${CDP_PORT:-9222}"
export SESSION_DIR="${SESSION_DIR:-/app/browser_profile}"

mkdir -p /app/data /app/browser_profile /app/screenshots

echo "[entrypoint] DISPLAY=$DISPLAY BROWSER_MODE=$BROWSER_MODE CDP_PORT=$CDP_PORT"

# Start virtual framebuffer if not already available
if ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
  echo "[entrypoint] Starting Xvfb on $DISPLAY"
  Xvfb "$DISPLAY" -screen 0 1366x850x24 -ac +extension GLX +render -noreset &
  sleep 1
fi

# Start real Chrome (Cloudflare-friendly) if CDP is not up yet
if ! curl -fsS "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
  CHROME_BIN="${CHROME_PATH:-}"
  if [[ -z "$CHROME_BIN" ]]; then
    for c in google-chrome-stable google-chrome chromium chromium-browser; do
      if command -v "$c" >/dev/null 2>&1; then
        CHROME_BIN="$(command -v "$c")"
        break
      fi
    done
  fi
  if [[ -z "${CHROME_BIN:-}" ]]; then
    echo "[entrypoint] ERROR: Chrome/Chromium not found in image"
    exit 1
  fi
  echo "[entrypoint] Starting $CHROME_BIN (CDP :$CDP_PORT)"
  "$CHROME_BIN" \
    --remote-debugging-port="$CDP_PORT" \
    --user-data-dir="$SESSION_DIR" \
    --no-first-run \
    --no-default-browser-check \
    --disable-dev-shm-usage \
    --disable-gpu \
    --no-sandbox \
    --window-size=1366,850 \
    "${BASE_URL:-https://www.usvisascheduling.com/en-US/}" \
    >/tmp/chrome.log 2>&1 &
  # Wait for CDP
  for i in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
      echo "[entrypoint] Chrome CDP is ready"
      break
    fi
    sleep 1
  done
fi

# Default command: long-running monitor
exec "$@"
