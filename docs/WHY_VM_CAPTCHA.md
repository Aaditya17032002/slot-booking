# Why VM login fails (and what to do instead)

## What worked on your PC

```text
Real Google Chrome (Windows desktop)
  + your home/residential IP
  + you clicking Cloudflare
  + scripts/monitor.py attached via CDP
```

That is a normal browser session. Cloudflare accepts it.

## What the Azure VM is doing

```text
Chrome inside Docker + Xvfb
  + Azure datacenter IP
  + --no-sandbox / container fingerprints
```

Even with noVNC, Cloudflare still treats this as a bot/datacenter client and shows CAPTCHA again.  
**Copying `browser_profile` from Windows usually fails too** (IP-bound clearance + Windows cookie encryption).

So: **infra/CI on the VM is fine; browser automation on that VM will keep hitting CAPTCHA.**

## Recommended architecture (what actually works)

Run the **browser + monitor on your Windows PC** (where login already succeeded).  
Use the VM only if you want — but **not** for Cloudflare/Chrome.

```text
Your PC (real Chrome, stay logged in)
        │
        ▼
scripts/monitor.py  →  Telegram alerts
```

### Keep it running on Windows

```powershell
cd D:\UCI\US-visa
.\.venv\Scripts\activate

# One-time / whenever session dies:
python scripts/login.py
# pass Cloudflare + login, leave Chrome open, press ENTER

# 24/7 monitor (leave this PowerShell open, or use Task Scheduler):
python scripts/monitor.py
```

Leave the Chrome window from `login.py` open. The monitor attaches to it.

### Optional: Windows Task Scheduler

1. Action: `D:\UCI\US-visa\.venv\Scripts\python.exe`  
2. Arguments: `scripts\monitor.py`  
3. Start in: `D:\UCI\US-visa`  
4. Run only when you are logged in (needs desktop Chrome session)

Or use `nssm` / a hidden PowerShell window at logon.

## What to do with the Azure container

- Stop it so it stops spamming Cloudflare Telegram alerts:

```powershell
ssh -i "$env:USERPROFILE\.ssh\feedforge-deploy\id_ed25519" azureuser@172.184.135.148 "sudo docker stop usvisa-monitor"
```

- Keep GitHub → Docker Hub CI if you want the image for later on a **residential** machine.  
- Do **not** expect Azure Docker to replace real Chrome for this site.

## If you must use a server later

You need **residential egress** (home IP / residential proxy) **and** a real interactive Chrome session on that IP — not a plain Azure public IP + container Chrome.
