# User & Operations Manual: Fluxara Automation Platform

Welcome to your custom, high-performance network automation engine. This platform provides an agile alternative to complex enterprise orchestration engines by using a decoupled, asynchronous Python design pattern to interact with your data infrastructure under a lightweight single-page visual layout.

---

## 🔐 1. Exchanging Credentials for Access Tokens (OAuth2)
To run automated tasks across the fleet or update system schedules, authorization guards must check active security clearances. Point a form POST request at the token route using your seed credentials to get a JSON Web Token (JWT):

```bash
curl -X POST "http://127.0.0" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=net_admin&password=VaultSecuredPassword123!"
```
**Expected Response Output payload:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "role": "admin"
}
```

---

## ⚡ 2. Dispatching On-Demand Nornir Tasks via the REST API
When executing configuration adjustments or operational compliance checks across your network, pass your access token inside an HTTP Authorization header. The input request payload will be parsed by Pydantic and passed down to location-sharded ZeroMQ processing engines instantly:

```bash
curl -X POST "http://127.0.0" \
     -H "Authorization: Bearer <your_access_token_string>" \
     -H "Content-Type: application/json" \
     -d '{
       "job_type": "backup_configs",
       "netbox_filters": {
         "site": "dfw",
         "role": "backbone-switch",
         "status": "active"
       },
       "extra_vars": {
         "configs": [
           "ntp server 10.10.10.1 prefer"
         ]
       }
     }'
```

### Underlying Automation Workflow Lifecycle:
1. FastAPI logs the job request intent inside **Percona PostgreSQL 18** and automatically writes an immutable log row into the **ActivityStream Compliance Table** detailing user actions.
2. The gateway parses the NetBox filters site parameter (`site: dfw`) and dynamically hits the specific localized **ZeroMQ regional PULL socket shard channel**.
3. The designated background worker daemon wakes up and pulls target host parameters dynamically from **NetBox** via runtime API calls.
4. The worker securely retrieves matching device passwords or enable keys from **HashiCorp Vault**, avoiding credential exposures across message layers.
5. Nornir launches its internal **ThreadedRunner** pool, orchestrating parallel multi-threaded SSH connection tunnels to target hardware interfaces via **Netmiko**.

---

## 📊 3. Interactive Single-Page HTMX Panel Monitoring
Navigating to `http://<server_host_ip>:8000/jobs/<job_id>` loads the complete visual terminal environment.
- **Token-Secured Live Log Streaming:** The interface extracts your access token from browser `localStorage` and appends it as a query parameter (`?token=<jwt>`). FastAPI drops any connection attempts lacking verification, while valid channels stream pre-rendered HTML log lines out of **Percona Valkey Pub/Sub** directly onto your scrolling panel without single-line JavaScript dependencies.
- **Dynamic Content Viewports:** Clicking the header navigation links (`[Schedules]`, `[Inventories]`, `[Projects]`) prompts HTMX to execute an asynchronous asynchronous GET request to FastAPI. The backend returns clean, partial HTML pane elements that overwrite the main viewport instantly without disrupting active console output streams or status widgets.
