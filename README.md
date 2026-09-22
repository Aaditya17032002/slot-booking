# US Visa Slot Monitor

Alert-only B1/B2 slot watcher for Kolkata + Mumbai.  
**Manual booking only.** Secrets stay in GitHub Secrets — not on the VM disk.

## Architecture

```text
GitHub (code + secrets)
    │  CI builds image → GHCR
    ▼
Azure Linux VM
    └── docker run usvisa-monitor
            ├── secrets as container env (from CI, not a .env file)
            ├── Google Chrome + Xvfb (Linux)
            └── Telegram alerts
```

## Local (Windows) — recommended for first login

```bash
python -m venv .venv && .\.venv\Scripts\activate
pip install -r requirements.txt
python scripts/login.py          # real Chrome, you pass Cloudflare
python scripts/check_slots.py
python scripts/monitor.py
```

## Production

Push to `main` → GitHub Actions builds/pushes `ghcr.io/<you>/us-visa-monitor` → SSH deploys to the VM.

See [docs/DEPLOY.md](docs/DEPLOY.md).

## Important

- Do **not** commit `.env`
- Chromium/Chrome works on Linux in Docker; Cloudflare may still need one interactive login after IP change
- Session cookies live in Docker volume `usvisa-profile` only
