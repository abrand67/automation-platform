# Installation Guide: Air-Gapped Fluxara Automation Platform

This document covers the step-by-step setup procedure required to natively deploy the custom Fluxara platform onto a single Linux virtual instance or bare-metal host machine (Ubuntu/RHEL).

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
sudo mkdir -p /opt/Fluxara/app/static
sudo mkdir -p /opt/Fluxara/app/templates
sudo mkdir -p /opt/Fluxara/workspaces
sudo useradd -r -s /bin/false automation || true
```

### Step 2: Configure Centralized Environment Profiles
Create your environment variables configuration file inside `/opt/Fluxara/app/.env` matching your enterprise data infrastructure parameters:
```ini
DATABASE_URL=postgresql+asyncpg://nornir_admin:Pass123!@127.0.0.1:5432/nornir_db
VALKEY_HOST=127.0.0.1
JWT_SECRET_KEY=SuperSecretProductionCryptographicKey999!!!
NETBOX_URL=https://your-netbox-server.local
NETBOX_TOKEN=0123456789abcdef0123456789abcdef01234567
VAULT_ADDR=http://127.0.0.1:8200
VAULT_TOKEN=your_static_worker_vault_token
```

### Step 3: Run the Automation Deployment Script
Make the native install/copy script executable and run it via root context to automate environment generation, script compilation, and systemd daemon initialization blocks:
```bash
sudo chmod +x ./install.sh
sudo ./install.sh
```

### Step 4: Initialize Schemas & Apply Role-Based Access Control Seeds
Execute the comprehensive DDL and DML data initializations directly within your Percona PostgreSQL shell to establish application boundaries:

```bash
# 1. Pipe the layout definitions to generate your tables, associations, and search indexes
psql -U nornir_admin -d nornir_db -f /opt/Fluxara/app/initialize_schema.sql

# 2. Bootstrap your root database system administrator user profile
sudo -u automation /opt/Fluxara/venv/bin/python /opt/Fluxara/app/seed_admin.py net_admin VaultSecuredPassword123!

# 3. Apply your corporate permission tiers, wildcard tokens, and link your admin profile
psql -U nornir_admin -d nornir_db -f /opt/Fluxara/app/seed_rbac_records.sql
```
---

## 🔍 System Verification & Log Verification
To confirm that your background task loop processes can bind to the local ZeroMQ sockets and query directory service handshakes seamlessly, check the host logging journal metrics:
```bash
# Check worker loop actions, connection logs, or Vault authentication exceptions
sudo journalctl -u Fluxara-worker-global.service -f -n 50

# Check web server routing outputs, API calls, or LDAP / RADIUS communication logs
sudo journalctl -u Fluxara-unit.service -f -n 50
```
