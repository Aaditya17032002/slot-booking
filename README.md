# US Visa Slot Monitor

Alert-only B1/B2 slot watcher for Kolkata + Mumbai.  
**Manual booking only.**

Repo: https://github.com/Aaditya17032002/slot-booking

## Registries

| What | Where |
|------|--------|
| Docker image | `docker.io/aditya17032002/us-visa-monitor` |
| Secrets | GitHub Actions secrets (not on the VM disk) |
| VM pull | Docker Hub **read-only** PAT |

## Local

```bash
python scripts/login.py
python scripts/check_slots.py
python scripts/monitor.py
```

## CI/CD

Push to `main` → build → push Docker Hub → SSH deploy to Azure.  
See [docs/DEPLOY.md](docs/DEPLOY.md).
