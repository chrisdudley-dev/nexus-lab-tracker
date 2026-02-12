# Nexus Lab Tracker — systemd + nginx wiring

Generated: 2026-02-12T07:43:30-05:00

## Why we use both Vite and nginx
- **Vite**: development server with hot reload (optional)
- **nginx**: always-on UI server at :8788 + reverse proxy for /api to :8787 (default viewing mode)

## Detected services
  nexus-lims-api.service                                      loaded    active   running Nexus LIMS API (localhost-only)

## systemd unit: nexus-lims-api.service
# /etc/systemd/system/nexus-lims-api.service
[Unit]
Description=Nexus LIMS API (localhost-only)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=christopher
Group=christopher
WorkingDirectory=/mnt/ssd/projects/nexus-lab-tracker
Environment=REPO_ROOT=/mnt/ssd/projects/nexus-lab-tracker
Environment=OLLAMA_HOST=http://127.0.0.1:11434
ExecStart=/usr/bin/python3 scripts/lims_api.py --port 8787
Restart=on-failure
RestartSec=2
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target

# /etc/systemd/system/nexus-lims-api.service.d/10-envfile.conf
[Service]
EnvironmentFile=/etc/nexus-lims-api.env

# /etc/systemd/system/nexus-lims-api.service.d/override.conf
[Service]
# no-overlap lock + stable restart behavior
ExecStart=
ExecStart=/usr/bin/flock -n /tmp/nexus-lims-api.lock /usr/bin/python3 scripts/lims_api.py --port 8787
Restart=on-failure
RestartSec=2

# hardening
NoNewPrivileges=yes
PrivateTmp=yes
ProtectHome=yes
ProtectSystem=strict

# allow writes only where the app should write
ReadWritePaths=/mnt/ssd/projects/nexus-lab-tracker/data \
 /mnt/ssd/projects/nexus-lab-tracker/exports \
 /mnt/ssd/projects/nexus-lab-tracker/report \
 /mnt/ssd/projects/nexus-lab-tracker/logs

## systemd status (top)
● nexus-lims-api.service - Nexus LIMS API (localhost-only)
     Loaded: loaded (/etc/systemd/system/nexus-lims-api.service; enabled; preset: enabled)
    Drop-In: /etc/systemd/system/nexus-lims-api.service.d
             └─10-envfile.conf, override.conf
     Active: active (running) since Tue 2026-02-10 21:00:40 EST; 1 day 10h ago
   Main PID: 441067 (flock)
      Tasks: 2 (limit: 9585)
        CPU: 9.659s
     CGroup: /system.slice/nexus-lims-api.service
             ├─441067 /usr/bin/flock -n /tmp/nexus-lims-api.lock /usr/bin/python3 scripts/lims_api.py --port 8787
             └─441072 /usr/bin/python3 scripts/lims_api.py --port 8787

Feb 10 21:05:03 jerboa flock[441072]: 127.0.0.1 - - [10/Feb/2026 21:05:03] "GET /health HTTP/1.1" 200 -
Feb 10 21:05:03 jerboa flock[441072]: 127.0.0.1 - - [10/Feb/2026 21:05:03] "GET /health HTTP/1.1" 200 -
Feb 10 21:06:41 jerboa flock[441072]: 127.0.0.1 - - [10/Feb/2026 21:06:41] "GET /health HTTP/1.1" 200 -
Feb 10 21:06:41 jerboa flock[441072]: 127.0.0.1 - - [10/Feb/2026 21:06:41] "GET /health HTTP/1.1" 200 -
Feb 11 15:49:47 jerboa flock[441072]: 127.0.0.1 - - [11/Feb/2026 15:49:47] "GET /health HTTP/1.1" 200 -
Feb 11 15:49:47 jerboa flock[441072]: 127.0.0.1 - - [11/Feb/2026 15:49:47] "GET /metrics HTTP/1.1" 200 -
Feb 11 16:02:19 jerboa flock[441072]: 127.0.0.1 - - [11/Feb/2026 16:02:19] "GET /health HTTP/1.1" 200 -
Feb 11 19:47:17 jerboa flock[441072]: 127.0.0.1 - - [11/Feb/2026 19:47:17] "GET /sample/list?limit=5 HTTP/1.1" 200 -
Feb 12 07:09:55 jerboa flock[441072]: 127.0.0.1 - - [12/Feb/2026 07:09:55] "GET /health HTTP/1.1" 200 -
Feb 12 07:09:55 jerboa flock[441072]: 127.0.0.1 - - [12/Feb/2026 07:09:55] "GET /sample/list?limit=1 HTTP/1.1" 200 -

## systemd wiring (paths + env)
Environment=REPO_ROOT=/mnt/ssd/projects/nexus-lab-tracker OLLAMA_HOST=http://127.0.0.1:11434
EnvironmentFiles=/etc/nexus-lims-api.env (ignore_errors=no)
FragmentPath=/etc/systemd/system/nexus-lims-api.service
DropInPaths=/etc/systemd/system/nexus-lims-api.service.d/10-envfile.conf /etc/systemd/system/nexus-lims-api.service.d/override.conf

## nginx site: /etc/nginx/sites-enabled/nexus-web-react
server {
  listen 127.0.0.1:8788;
  listen 192.168.1.191:8788;
  server_name _;

  root /var/www/nexus-web-react;
  index index.html;

  # LAN-only (adjust subnet if needed)
  allow 127.0.0.1;
  allow ::1;
  allow 192.168.1.0/24;
  deny all;

  location / {
    try_files $uri $uri/ /index.html;
  }

  # API proxy to localhost-only backend
  location /api/ {
    proxy_pass http://127.0.0.1:8787/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}

## Smoke tests
# Backend direct
curl -fsS http://127.0.0.1:8787/health | head -c 240; echo

# Through nginx (/api proxy)
curl -fsS http://127.0.0.1:8788/api/health | head -c 240; echo
curl -fsS "http://127.0.0.1:8788/api/sample/list?limit=1" | head -c 240; echo

# Deploy UI to nginx webroot
./scripts/web_deploy_nginx.sh
