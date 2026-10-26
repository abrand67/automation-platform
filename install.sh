#!/usr/bin/env bash
#
# Copyright 2026 Allan Brand
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://apache.org
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific permissions and
# limitations under the License.

set -euo pipefail

APP_ROOT="/opt/Fluxara"
SRC_ROOT="${APP_ROOT}/app"
STATIC_ROOT="${SRC_ROOT}/static"
TEMPLATES_ROOT="${SRC_ROOT}/templates"
WORKSPACES_ROOT="${APP_ROOT}/workspaces"
VENV_PATH="${APP_ROOT}/venv"

echo "========================================================================="
echo "⚡ Fluxara Complete Deployment, Copy, & Rebrand Script"
echo "========================================================================="

if [[ $EUID -ne 0 ]]; then
   echo "❌ CRITICAL ERROR: This deployment script must be executed via sudo or root." 1>&2
   exit 1
fi

if [ -f /etc/debian_version ]; then
    echo "[System] Installing system binary packages (Debian/Ubuntu)..."
    apt-get update -y
    apt-get install -y build-essential libpq-dev libldap2-dev libsasl2-dev libssl-dev git curl python3-venv python3-dev unit unit-python3
elif [ -f /etc/redhat-release ]; then
    echo "[System] Installing system binary packages (RHEL/Rocky Linux)..."
    dnf groupinstall -y "Development Tools"
    dnf install -y postgresql-devel openldap-devel cyrus-sasl-devel openssl-devel git curl python3-devel unit
else
    echo "❌ CRITICAL ERROR: Unsupported Linux distribution." 1>&2
    exit 1
fi

echo "[System] Building directory structures and automation user account..."
mkdir -p "${STATIC_ROOT}" "${TEMPLATES_ROOT}" "${WORKSPACES_ROOT}"

if ! id -u automation &>/dev/null; then
    useradd -r -s /bin/false automation
fi

echo "[Project] Deploying software application and template assets..."
if [ -f "./unit-config.json" ]; then cp "./unit-config.json" "${APP_ROOT}/"; fi
if [ -f "./.env" ]; then cp "./.env" "${SRC_ROOT}/"; fi

for py_file in database.py main.py schemas.py security.py tasks.py nornir_zmq_worker.py auth_providers.py git_manager.py seed_admin.py read_audit_stream.py; do
    if [ -f "./${py_file}" ]; then
        cp "./${py_file}" "${SRC_ROOT}/"
    elif [ -f "./app/${py_file}" ]; then
        cp "./app/${py_file}" "${SRC_ROOT}/"
    fi
done

if [ -d "./templates" ]; then
    cp -r ./templates/* "${TEMPLATES_ROOT}/"
elif [ -d "./app/templates" ]; then
    cp -r ./app/templates/* "${TEMPLATES_ROOT}/"
fi

echo "[System] Constructing isolated python runtime environment..."
python3 -m venv "${VENV_PATH}"
"${VENV_PATH}/bin/pip" install --upgrade pip
"${VENV_PATH}/bin/pip" install fastapi hvac zmq redis nornir nornir-netbox nornir-netmiko sqlalchemy asyncpg jinja2 pydantic passlib bcrypt python-jose apscheduler ldap3 pyradius python-dotenv python-multipart httpx

echo "[System] Downloading air-gapped web assets natively..."
curl -sSL -o "${STATIC_ROOT}/htmx.min.js" https://unpkg.com
curl -sSL -o "${STATIC_ROOT}/ws.js" https://unpkg.com

echo "[System] Regulating directory file security metrics..."
chown -R automation:automation "${APP_ROOT}"
chmod 750 "${WORKSPACES_ROOT}"
if [ -f "${SRC_ROOT}/.env" ]; then chmod 600 "${SRC_ROOT}/.env"; fi

echo "[System] Deploying systemd unit service daemons..."
cat << 'EOF' > /etc/systemd/system/Fluxara-unit.service
[Unit]
Description=NGINX Unit Application Server - Fluxara FastAPI Gateway
After=network.target

[Service]
Type=forking
EnvironmentFile=/opt/Fluxara/app/.env
ExecStart=/usr/sbin/unitd --control unix:/var/run/control.unit.sock
ExecStartPost=/usr/bin/curl -X PUT --data-binary @/opt/Fluxara/unit-config.json --unix-socket /var/run/control.unit.sock http://localhost/config
ExecReload=/usr/bin/curl -X PUT --data-binary @/opt/Fluxara/unit-config.json --unix-socket /var/run/control.unit.sock http://localhost/config
KillMode=process
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat << 'EOF' > /etc/systemd/system/Fluxara-worker-global.service
[Unit]
Description=Long-Running ZeroMQ Shard Worker - Fluxara Global Fabric
After=network.target

[Service]
Type=simple
User=automation
Group=automation
WorkingDirectory=/opt/Fluxara/app
EnvironmentFile=/opt/Fluxara/app/.env
ExecStart=/opt/Fluxara/venv/bin/python nornir_zmq_worker.py /opt/Fluxara/venv/bin/python nornir_zmq_worker.py tcp://127.0.0.1:5557
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "[System] Refreshing system services loops..."
systemctl daemon-reload

echo "========================================================================="
echo "✅ SUCCESS: Fluxara system code deployed and rebranded cleanly."
echo "========================================================================="
