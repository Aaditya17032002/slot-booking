# Deployment (Docker Hub + Azure)

## Image

`docker.io/aditya17032002/us-visa-monitor:latest`

- **Push (CI):** `DOCKERHUB_USERNAME` + `DOCKERHUB_TOKEN_RW`
- **Pull (VM):** same username + `DOCKERHUB_TOKEN_RO`

## Secrets (GitHub Actions only)

Never write a long-lived `.env` on the VM. CI injects env into `docker run` via RAM (`/dev/shm`) then shreds it.

Required: `SSH_*`, visa creds, Telegram, `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN_RW`, `DOCKERHUB_TOKEN_RO`, `CONSULATES`, `VISA_*`.

## Linux note

The image includes **Google Chrome + Xvfb**. Cloudflare may still need one interactive login after a new datacenter IP; session then sits in Docker volume `usvisa-profile`.
