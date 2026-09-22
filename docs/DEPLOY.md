# Deployment notes (Linux Azure VM)

## What lives where

| Thing | Where |
|-------|--------|
| Source code | GitHub only |
| Docker image | GHCR (`ghcr.io/<you>/us-visa-monitor`) |
| Secrets (password, Telegram, …) | **GitHub Secrets** → injected at deploy into the container env |
| On the VM disk | Docker engine + named volumes for Chrome profile/state only |
| `.env` file on VM | **Never written** (ephemeral `/dev/shm` then shredded) |

## One-time: GitHub Secrets

Set by the bootstrap script / `gh secret set`:

- `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`
- `USVISA_USERNAME`, `USVISA_PASSWORD`
- `SECURITY_A_PET`, `SECURITY_A_FOOD`, `SECURITY_A_WORK`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `CONSULATES`, `VISA_CATEGORY`, `VISA_TYPE`

## Pipeline

Push to `main` → build image → push GHCR → SSH to VM → `docker pull` → `docker run` with env from secrets.

## Linux + Cloudflare reality

Chromium/Chrome **does** run on Linux in this image (Google Chrome + Xvfb).

Cloudflare may still require a **one-time interactive login** inside the container after first deploy (new datacenter IP). Session cookies then live in the `usvisa-profile` Docker volume — not in GitHub secrets.

Helpful commands on the VM:

```bash
sudo docker logs -f usvisa-monitor
sudo docker exec -it usvisa-monitor bash
```

If Telegram reports Cloudflare/session expired, re-login once via VNC/Bastion against the running Chrome profile volume, or run a one-off interactive container sharing `usvisa-profile`.
