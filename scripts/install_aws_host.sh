#!/usr/bin/env bash
# Run through AWS Systems Manager on the dedicated Amazon Linux 2023 demo instance.
set -euo pipefail

: "${COHERENT_GIT_SHA:?}"
: "${COHERENT_PUBLIC_ORIGIN:?}"
: "${COHERENT_ORIGIN_TOKEN:?}"
: "${COHERENT_PORTAL_CONFIG_B64:?}"
: "${COHERENT_KB_ID:?}"

dnf install -y git nginx python3.12 python3.12-pip nodejs22 nodejs22-npm
alternatives --set node /usr/bin/node-22
alternatives --set npm /usr/bin/npm-22

if [ ! -d /opt/coherent/.git ]; then
  git clone https://github.com/Da0t/LPL-Hackathon.git /opt/coherent
fi
cd /opt/coherent
git fetch --depth 1 origin "$COHERENT_GIT_SHA"
git checkout --force "$COHERENT_GIT_SHA"

python3.12 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check --no-cache-dir -r requirements.txt
npm-22 install --global pnpm@10
cd web
pnpm install --frozen-lockfile
pnpm run build
cd /opt/coherent
chown -R ec2-user:ec2-user /opt/coherent/web/.next/cache

install -d -m 750 -o ec2-user -g ec2-user /var/lib/coherent
install -d -m 750 /etc/coherent
printf '%s' "$COHERENT_PORTAL_CONFIG_B64" | base64 -d > /etc/coherent/portal-aws.json
chmod 640 /etc/coherent/portal-aws.json
cat > /etc/coherent/backend.env <<EOF
AWS_REGION=us-east-1
AWS_DEFAULT_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
BEDROCK_KNOWLEDGE_BASE_ID=$COHERENT_KB_ID
SAMEPAGE_AI_MODE=bedrock
SAMEPAGE_DB_PATH=/var/lib/coherent/samepage.db
COHERENT_PORTAL_CONFIG=/etc/coherent/portal-aws.json
COHERENT_ALLOWED_ORIGINS=$COHERENT_PUBLIC_ORIGIN
COHERENT_SECURE_COOKIES=1
EOF
chmod 640 /etc/coherent/backend.env

cat > /etc/systemd/system/coherent-api.service <<'EOF'
[Unit]
Description=Coherent FastAPI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ec2-user
Group=ec2-user
WorkingDirectory=/opt/coherent
EnvironmentFile=/etc/coherent/backend.env
ExecStart=/opt/coherent/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=full
ReadWritePaths=/var/lib/coherent

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/coherent-web.service <<'EOF'
[Unit]
Description=Coherent Next.js
After=network-online.target coherent-api.service
Wants=network-online.target

[Service]
Type=simple
User=ec2-user
Group=ec2-user
WorkingDirectory=/opt/coherent/web
Environment=NODE_ENV=production
ExecStart=/usr/bin/node-22 /opt/coherent/web/node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3200
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/nginx/nginx.conf <<'EOF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /run/nginx.pid;
events { worker_connections 1024; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    sendfile on;
    include /etc/nginx/conf.d/*.conf;
}
EOF
rm -f /etc/nginx/conf.d/default.conf
cat > /etc/nginx/conf.d/coherent.conf <<EOF
server {
    listen 80 default_server;
    server_name _;
    if (\$http_x_coherent_origin != "$COHERENT_ORIGIN_TOKEN") { return 403; }
    location / {
        proxy_pass http://127.0.0.1:3200;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;
    }
}
EOF
nginx -t
systemctl daemon-reload
systemctl enable --now coherent-api coherent-web nginx
systemctl restart coherent-api coherent-web nginx

for attempt in $(seq 1 30); do
  if curl --fail --silent --max-time 5 http://127.0.0.1:8000/health >/dev/null && \
     curl --fail --silent --max-time 5 -H "X-Coherent-Origin: $COHERENT_ORIGIN_TOKEN" http://127.0.0.1/login >/dev/null; then
    echo "Coherent host ready at commit $COHERENT_GIT_SHA"
    exit 0
  fi
  sleep 5
done
systemctl --no-pager --full status coherent-api coherent-web nginx || true
exit 1
