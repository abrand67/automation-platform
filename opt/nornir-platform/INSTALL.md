# Installation Guide: Air-Gapped Nornir Automation Platform

This document covers the step-by-step setup procedure required to natively deploy the custom Nornir platform onto a single Linux virtual instance or bare-metal host machine (Ubuntu/RHEL).

---

## 📋 System Prerequisites & Binaries
Before configuring the Python application layers, ensure the following core infrastructure tools are installed locally on your operating system via native package managers (`apt` or `dnf`):
1. **Percona Distribution for PostgreSQL 18** (Configured with local user `nornir_admin` and database name `nornir_db`)
2. **Percona Valkey** (Running on local interface port `6379`)
3. **HashiCorp Vault** (Running on port `8200` with an active KV Version 2 secrets engine engine set up at path `network/credentials`)
4. **NGINX Unit Application Server** (`nginx-unit` and `unit-python3` development execution modules)

### Linux Build Dependencies (Required for Enterprise LDAP / Auth Modules):
```bash
# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y build-essential libpq-dev libldap2-dev libsasl2-dev libssl-dev git curl

# RHEL / Rocky Linux
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y postgresql-devel openldap-devel cyrus-sasl-devel openssl-devel git curl
```

---

## 🛠️ Native Deployment Setup

### Step 1: Initialize System Filesystem Directories & Users
Create required project directories, local source workspaces, and restrict runtime execution privileges under a dedicated, non-root system automation user account context:
```bash
sudo mkdir -p /opt/nornir-platform/app/static
sudo mkdir -p /opt/nornir-platform/app/templates
sudo mkdir -p /opt/nornir-platform/workspaces
sudo useradd -r -s /bin/false automation || true
```

### Step 2: Configure the Python Virtual Environment & Download Air-Gapped Assets
Initialize an isolated workspace environment, install code dependencies, and download frontend libraries directly into local static directories so the layout runs 100% offline without external CDN calls:
```bash
cd /opt/nornir-platform
sudo -u automation python3 -m venv venv
sudo -u automation ./venv/bin/pip install --upgrade pip
sudo -u automation ./venv/bin/pip install fastapi hvac zmq redis nornir nornir-netbox nornir-netmiko sqlalchemy asyncpg jinja2 pydantic passlib bcrypt python-jose apscheduler ldap3 pyradius

# Download scripting assets directly to create a disconnected web dashboard
cd /opt/nornir-platform/app/static/
sudo curl -sSL -o htmx.min.js https://unpkg.com### Step 3: Register Native Linux Systemd Services
To configure the web interface runtime and background execution queues to launch automatically on server boot, create and deploy the service unit configuration blocks:
```bash
# Register the service configuration blocks to system filesystems
sudo cp /opt/nornir-platform/infrastructure/systemd/nornir-unit.service /etc/systemd/system/
sudo cp /opt/nornir-platform/infrastructure/systemd/nornir-worker.service /etc/systemd/system/

# Reload systemd structures and execute background process state triggers
sudo systemctl daemon-reload
sudo systemctl enable --now nornir-unit.service
sudo systemctl enable --now nornir-worker.service
```

### Step 4: Populate the Root Administrative Account
Run the secure application database seed script using your environment path to add an initial administrator account to your Percona PostgreSQL engine instance:
```bash
cd /opt/nornir-platform/app
sudo -u automation /opt/nornir-platform/venv/bin/python seed_admin.py net_admin VaultSecuredPassword123!
```

---

## 🔍 System Verification & Log Verification
To confirm that your background task loop processes can bind to the local ZeroMQ sockets and query directory service handshakes seamlessly, check the host logging journal metrics:
```bash
# Check worker loop actions, connection logs, or Vault authentication exceptions
sudo journalctl -u nornir-worker.service -f -n 50

# Check web server routing outputs, API calls, or LDAP / RADIUS communication logs
sudo journalctl -u nornir-unit.service -f -n 50
```

sudo curl -sSL -o ws.js https://unpkg.com
sudo chown -R automation:automation /opt/nornir-platform
```

