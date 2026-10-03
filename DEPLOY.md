# Deploy Discovery Engine on your VPS (praveen / srv1519052)

This guide matches your site layout:

| Path | Purpose |
|------|---------|
| `/var/www/mysite/` | Main site (`index.html`, `assets/`) |
| `/var/www/mysite/projects/` | Project apps (`SSM`, `VO2`, `vivah mcp`, `webOss`, …) |
| **`/var/www/mysite/projects/Discovery`** | **This app** (clone from GitHub) |

- **Repo:** [github.com/praveenkumarbihari/Discovery](https://github.com/praveenkumarbihari/Discovery)
- **Process:** FastAPI on **`127.0.0.1:8765`** (live web scrape + LLM analyze; no DuckDB required for the UI)
- **Public URL (recommended):** `https://YOUR_DOMAIN/projects/discovery/` on the same nginx vhost as `mysite`

---

## Quick checklist

1. Clone into `/var/www/mysite/projects/Discovery`
2. Create `.venv`, `pip install -r requirements.txt`
3. Copy `.env` with LLM keys + `DISCOVERY_BASE_PATH` + `OPENROUTER_HTTP_REFERER`
4. Test with `curl http://127.0.0.1:8765/api/health`
5. Add **systemd** unit `discovery-engine.service`
6. Add **nginx** `location /projects/discovery/` to your existing `mysite` server block
7. Reload nginx; open the public URL; hard-refresh (`Ctrl+F5`) after updates

---

## 1. Prerequisites (on the VPS)

SSH as `praveen@srv1519052`:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

`nginx` is likely already installed for `/var/www/mysite`. If not:

```bash
sudo apt install -y nginx
```

HTTPS (if not already on the main site):

```bash
sudo apt install -y certbot python3-certbot-nginx
```

---

## 2. Clone the repo

```bash
cd /var/www/mysite/projects
git clone https://github.com/praveenkumarbihari/Discovery.git Discovery
cd Discovery
```

If the folder already exists, update instead:

```bash
cd /var/www/mysite/projects/Discovery
git pull origin main
```

Ensure `praveen` can write here (for `.venv` and optional cache):

```bash
sudo chown -R praveen:praveen /var/www/mysite/projects/Discovery
```

---

## 3. Python virtual environment

```bash
cd /var/www/mysite/projects/Discovery
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Environment (`.env`)

```bash
cp .env.example .env
nano .env
```

**Required (at least one LLM):**

```env
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-4o-mini
```

**Optional fallback:**

```env
GEMINI_API_KEY=...
```

**Production (set to your real public URL):**

```env
OPENROUTER_HTTP_REFERER=https://YOUR_DOMAIN/projects/discovery/
OPENROUTER_APP_TITLE=Google Photos Discovery Engine
```

Lock permissions:

```bash
chmod 600 .env
```

---

## 5. Manual test (before systemd)

```bash
cd /var/www/mysite/projects/Discovery
source .venv/bin/activate
export DISCOVERY_BASE_PATH=/projects/discovery/
python3 -m uvicorn src.web_app:app --host 127.0.0.1 --port 8765
```

In another SSH session:

```bash
curl -s http://127.0.0.1:8765/api/health
```

Expect JSON with `"ok": true`. Stop the test with `Ctrl+C`.

**From your laptop (no nginx yet):**

```bash
ssh -L 8765:127.0.0.1:8765 praveen@srv1519052
```

Open `http://127.0.0.1:8765/` on your PC.

---

## 6. systemd (always on)

Create `/etc/systemd/system/discovery-engine.service`:

```ini
[Unit]
Description=Google Photos Discovery Engine (FastAPI)
After=network.target

[Service]
Type=simple
User=praveen
Group=praveen
WorkingDirectory=/var/www/mysite/projects/Discovery
Environment=PATH=/var/www/mysite/projects/Discovery/.venv/bin
Environment=DISCOVERY_BASE_PATH=/projects/discovery/
EnvironmentFile=/var/www/mysite/projects/Discovery/.env
ExecStart=/var/www/mysite/projects/Discovery/.venv/bin/python -m uvicorn src.web_app:app --host 127.0.0.1 --port 8765
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable discovery-engine
sudo systemctl start discovery-engine
sudo systemctl status discovery-engine
```

Logs:

```bash
journalctl -u discovery-engine -f
```

---

## 7. nginx — subpath under `mysite` (recommended)

Do **not** expose port **8765** on the public firewall. Only nginx talks to the app.

Find the server block that serves `/var/www/mysite` (often `/etc/nginx/sites-enabled/default` or a custom `mysite` file):

```bash
sudo nginx -T 2>/dev/null | grep -E "root /var/www/mysite|server_name"
```

Inside that `server { ... }` block, **add** (keep your existing `root` and `location /` for the main site):

```nginx
    # Discovery Engine — sibling to other projects under /projects/
    location /projects/discovery/ {
        proxy_pass http://127.0.0.1:8765/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        client_max_body_size 4m;
    }
```

Reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

**Public URL:** `https://YOUR_DOMAIN/projects/discovery/`  
(Replace `YOUR_DOMAIN` with the hostname you already use for `mysite`.)

**Link from your portfolio:** add a card on `index.html` pointing to `/projects/discovery/` (same pattern as `webOss`, etc.).

### Optional: redirect without trailing slash

```nginx
    location = /projects/discovery {
        return 301 /projects/discovery/;
    }
```

---

## 8. Alternative: subdomain (simpler URLs)

If you prefer `https://discovery.YOUR_DOMAIN/` instead of a subpath:

1. DNS **A record** → your VPS IP  
2. New server block:

```nginx
server {
    listen 80;
    server_name discovery.YOUR_DOMAIN;

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

3. Remove `DISCOVERY_BASE_PATH` from the systemd unit (or leave it unset).  
4. Set `OPENROUTER_HTTP_REFERER=https://discovery.YOUR_DOMAIN/` in `.env`.  
5. `sudo certbot --nginx -d discovery.YOUR_DOMAIN`

---

## 9. Firewall

If you use UFW:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

Port **8765** should stay bound to **127.0.0.1** only (default in this guide).

---

## 10. Deploy updates

On the VPS:

```bash
cd /var/www/mysite/projects/Discovery
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart discovery-engine
```

Hard refresh the browser (`Ctrl+F5`) after static file changes.

---

## 11. Troubleshooting

| Symptom | What to do |
|--------|------------|
| Blank page / 404 on CSS or JS | Confirm `DISCOVERY_BASE_PATH=/projects/discovery/` in systemd; nginx `location` must end with `/` and `proxy_pass` must be `http://127.0.0.1:8765/` |
| 502 Bad Gateway | `sudo systemctl status discovery-engine`; `curl http://127.0.0.1:8765/api/health` |
| Analyze fails | Check `.env` keys; `journalctl -u discovery-engine -n 100` |
| Discover returns few/zero rows | Reddit often blocks datacenter IPs; Stack Exchange + HN + Play Store usually still work |
| Slow analyze | Normal for many rows; nginx timeouts are 300s above |

**Health check through nginx:**

```bash
curl -s https://YOUR_DOMAIN/projects/discovery/api/health
```

---

## 12. Optional CLI (DuckDB corpus)

The web UI does **not** need DuckDB. For offline bulk collect only:

```bash
cd /var/www/mysite/projects/Discovery
source .venv/bin/activate
python3 -m engine collect --yes
```

See `config.yaml` and `README.md`.

---

## Local dev vs VPS

| | Local (Windows) | VPS |
|--|-----------------|-----|
| Run | `py -3 -m src.web_app` | systemd + uvicorn on 8765 |
| URL | `http://127.0.0.1:8765` | `https://YOUR_DOMAIN/projects/discovery/` |
| Subpath env | omit `DISCOVERY_BASE_PATH` | set in systemd |
