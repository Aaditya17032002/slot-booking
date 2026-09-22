#!/usr/bin/env bash
# Linux container entrypoint:
#   MODE=monitor (default) — Chrome + slot monitor
#   MODE=login            — Chrome + noVNC so you can pass Cloudflare manually
set -euo pipefail

export DISPLAY="${DISPLAY:-:99}"
export BROWSER_MODE="${BROWSER_MODE:-cdp}"
export HEADLESS="${HEADLESS:-false}"
export CDP_PORT="${CDP_PORT:-9222}"
export SESSION_DIR="${SESSION_DIR:-/app/browser_profile}"
export MODE="${MODE:-monitor}"
export NOVNC_PORT="${NOVNC_PORT:-6080}"
export VNC_PORT="${VNC_PORT:-5900}"

mkdir -p /app/data /app/browser_profile /app/screenshots

echo "[entrypoint] MODE=$MODE DISPLAY=$DISPLAY CDP_PORT=$CDP_PORT"

# Start virtual framebuffer if not already available
if ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
  echo "[entrypoint] Starting Xvfb on $DISPLAY"
  Xvfb "$DISPLAY" -screen 0 1366x850x24 -ac +extension GLX +render -noreset &
  sleep 1
fi

start_chrome() {
  if curl -fsS "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
    echo "[entrypoint] Chrome CDP already up"
    return 0
  fi
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
  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${CDP_PORT}/json/version" >/dev/null 2>&1; then
      echo "[entrypoint] Chrome CDP is ready"
      return 0
    fi
    sleep 1
  done
  echo "[entrypoint] WARNING: Chrome CDP not ready; see /tmp/chrome.log"
}

start_vnc() {
  echo "[entrypoint] Starting x11vnc + noVNC on :$NOVNC_PORT (bind via -p 127.0.0.1:6080:6080)"
  x11vnc -display "$DISPLAY" -forever -shared -rfbport "$VNC_PORT" -nopw -listen 0.0.0.0 \
    >/tmp/x11vnc.log 2>&1 &
  # websockify serves noVNC static UI
  if [[ -d /usr/share/novnc ]]; then
    websockify --web=/usr/share/novnc "0.0.0.0:${NOVNC_PORT}" "127.0.0.1:${VNC_PORT}" \
      >/tmp/novnc.log 2>&1 &
  else
    echo "[entrypoint] ERROR: noVNC not installed in image"
    exit 1
  fi
  echo "[entrypoint] Open via SSH tunnel → http://127.0.0.1:${NOVNC_PORT}/vnc.html"
}

start_chrome

if [[ "$MODE" == "login" ]]; then
  start_vnc
  echo "[entrypoint] LOGIN MODE — complete Cloudflare + sign-in in the browser UI."
  echo "[entrypoint] When done, set MODE=monitor and redeploy/restart the container."
  # Keep container alive; do not start the poller
  exec tail -f /tmp/chrome.log /tmp/x11vnc.log /tmp/novnc.log
fi

# Optional: VNC also available during monitor (for emergency re-login)
if [[ "${ENABLE_VNC:-true}" == "true" ]]; then
  start_vnc || true
fi

exec "$@"
