# Deploy Discovery Engine on a Linux VPS

Target layout: **`~/projects/discovery-engine`** (or `/home/<user>/projects/discovery-engine`).

The web UI is **live scrape only** (no DuckDB required). It listens on **port 8765** behind **nginx** on ports 80/443.

---

## 1. VPS prerequisites

Ubuntu 22.04/24.04 (or similar):

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git nginx
```

Optional HTTPS:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

---

## 2. Copy the project to `~/projects`

**Option A — Git (recommended if you have a remote):**

```bash
mkdir -p ~/projects
cd ~/projects
git clone <YOUR_REPO_URL> discovery-engine
cd discovery-engine
```

**Option B — From your PC (rsync over SSH):**

```bash
# Run on your Windows PC (Git Bash / WSL), adjust user and VPS IP
rsync -avz --exclude .venv --exclude __pycache__ --exclude data/engine.duckdb \
  "/d/PM/Discovery Engine/" user@YOUR_VPS_IP:~/projects/discovery-engine/
```

**Option C — Zip upload:** zip the folder (without `.venv`), upload via SFTP, unzip under `~/projects/discovery-engine`.

---

## 3. Python environment

```bash
cd ~/projects/discovery-engine
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Environment variables

```bash
cp .env.example .env
nano .env
```

Set at least one LLM provider:

```env
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-4o-mini

# optional fallback
GEMINI_API_KEY=...
```

For production, set OpenRouter referer to your public URL:

```env
OPENROUTER_HTTP_REFERER=https://your-domain.com
OPENROUTER_APP_TITLE=Google Photos Discovery Engine
```

Lock down permissions:

```bash
chmod 600 .env
```

---

## 5. Test run (manual)

```bash
cd ~/projects/discovery-engine
source .venv/bin/activate
python3 -m uvicorn src.web_app:app --host 127.0.0.1 --port 8765
```

On the VPS:

```bash
curl -s http://127.0.0.1:8765/api/health
```

From your laptop (SSH tunnel, no nginx yet):

```bash
ssh -L 8765:127.0.0.1:8765 user@YOUR_VPS_IP
# then open http://127.0.0.1:8765 on your PC
```

Stop the test with `Ctrl+C`.

---

## 6. systemd service (always on)

Create `/etc/systemd/system/discovery-engine.service`:

```ini
[Unit]
Description=Discovery Engine (FastAPI)
After=network.target

[Service]
Type=simple
User=YOUR_LINUX_USER
WorkingDirectory=/home/YOUR_LINUX_USER/projects/discovery-engine
Environment=PATH=/home/YOUR_LINUX_USER/projects/discovery-engine/.venv/bin
ExecStart=/home/YOUR_LINUX_USER/projects/discovery-engine/.venv/bin/python -m uvicorn src.web_app:app --host 127.0.0.1 --port 8765
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Replace `YOUR_LINUX_USER` with your login (e.g. `ubuntu`).

```bash
sudo systemctl daemon-reload
sudo systemctl enable discovery-engine
sudo systemctl start discovery-engine
sudo systemctl status discovery-engine
journalctl -u discovery-engine -f
```

---

## 7. nginx reverse proxy

Create `/etc/nginx/sites-available/discovery-engine`:

```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_VPS_IP;

    client_max_body_size 4m;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

Enable and reload:

```bash
sudo ln -sf /etc/nginx/sites-available/discovery-engine /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Open **`http://YOUR_VPS_IP`** (or your domain) in a browser.

**HTTPS (with a domain):**

```bash
sudo certbot --nginx -d your-domain.com
```

---

## 8. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

Do **not** expose port 8765 publicly if nginx is in front (keep app on `127.0.0.1` only).

---

## 9. Updates after code changes

```bash
cd ~/projects/discovery-engine
source .venv/bin/activate
git pull   # or rsync again
pip install -r requirements.txt
sudo systemctl restart discovery-engine
```

Hard refresh the browser (`Ctrl+F5`) after static file changes.

---

## 10. Troubleshooting

| Issue | What to check |
|--------|----------------|
| Analyze fails | `.env` keys, `journalctl -u discovery-engine` |
| Discover returns nothing | Reddit/Play may block datacenter IPs; try Stack Exchange + HN only |
| 502 from nginx | `systemctl status discovery-engine`, port 8765 listening |
| Slow analyze | Normal for many rows; nginx timeouts set to 300s above |

**Logs:**

```bash
journalctl -u discovery-engine -n 100 --no-pager
```

---

## Optional: run on a subpath

If the app must live at `https://example.com/projects/discovery/` you need a reverse-proxy path strip and possibly FastAPI `root_path` — simpler to use a subdomain (`discovery.example.com`) or dedicated port behind nginx on `/`.
