# How to log in on the Azure VM (save session in Docker volume)

Credentials/session are stored in the Docker volume `usvisa-profile`  
(Chrome profile inside the container) — **not** as a `.env` password file on disk.

## Steps (from your Windows PC)

### 1) SSH tunnel (keep this window open)

```powershell
ssh -i "$env:USERPROFILE\.ssh\feedforge-deploy\id_ed25519" -L 6080:127.0.0.1:6080 azureuser@172.184.135.148
```

### 2) Open Chrome on your PC

Go to: **http://127.0.0.1:6080/vnc.html**  
Click **Connect** (no VNC password).

You are now looking at Chrome **inside the VM container**.

### 3) Log in there

1. Pass Cloudflare (“Just a moment…” / checkbox)  
2. Sign in + security questions  
3. Wait until you see your visa dashboard / appointments  

That session is written into `usvisa-profile` on the server.

### 4) Confirm monitor mode

If the container was started with `MODE=login`, switch back to monitoring:

```powershell
ssh -i "$env:USERPROFILE\.ssh\feedforge-deploy\id_ed25519" azureuser@172.184.135.148 "sudo docker stop usvisa-monitor; sudo docker rm usvisa-monitor"
```

Then re-run GitHub Action **Build and deploy** (or push to `main`) so it starts again with `MODE=monitor`.

Or, after this image update, monitor mode already exposes noVNC — you can re-login anytime via the tunnel without switching modes; then wait for the next poll (or restart):

```powershell
ssh -i "$env:USERPROFILE\.ssh\feedforge-deploy\id_ed25519" azureuser@172.184.135.148 "sudo docker restart usvisa-monitor"
```

### 5) Check Telegram / logs

You should get a normal “check complete” (or new slot) instead of Cloudflare alerts.

```powershell
ssh -i "$env:USERPROFILE\.ssh\feedforge-deploy\id_ed25519" azureuser@172.184.135.148 "sudo docker logs --tail 50 usvisa-monitor"
```

## Security note

Port `6080` is bound to **127.0.0.1 on the VM only** — not open to the public internet.  
You reach it only through your SSH tunnel.
