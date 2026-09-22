# Linux production image — Google Chrome + Xvfb + Playwright CDP attach
FROM mcr.microsoft.com/playwright/python:v1.49.1-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    BROWSER_MODE=cdp \
    HEADLESS=false \
    CDP_PORT=9222 \
    SESSION_DIR=/app/browser_profile \
    STATE_FILE=/app/data/slot_state.json

WORKDIR /app

# Virtual display + Chrome dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
      xvfb \
      x11-utils \
      curl \
      gnupg \
      ca-certificates \
      fonts-liberation \
      libnss3 \
      libatk-bridge2.0-0 \
      libgtk-3-0 \
      libx11-xcb1 \
      libxcomposite1 \
      libxdamage1 \
      libxrandr2 \
      libgbm1 \
      libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Google Chrome (stable) — closer to a real browser for Cloudflare
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
      | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium

COPY src ./src
COPY scripts ./scripts
COPY main.py .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /app/data /app/browser_profile /app/screenshots

# No .env baked in — secrets come from runtime env (CI/CD)
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "scripts/monitor.py"]
