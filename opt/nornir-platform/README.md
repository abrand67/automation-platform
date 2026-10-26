# Nornir Enterprise Automation Platform (AWX-Lite)

A high-performance, single-server, air-gapped network automation engine. This platform replaces heavy enterprise suites by coupling an asynchronous **FastAPI** gateway and **ZeroMQ** execution pipeline with a 100% native **HTML5/CSS3** dashboard powered entirely by **HTMX**. 

Infrastructure inventories are drawn dynamically from **NetBox**, target device credentials/certificates are fetched on-demand from **HashiCorp Vault**, and state tracking data is handled via **Percona Distribution for PostgreSQL 18** and **Percona Valkey**.

---

## 🔐 1. Authentication & Enterprise Directory Integration
The platform bypasses localized silo accounts by integrating directly with enterprise directory infrastructures. Login handshakes dynamically fallback across providers in this precise order:
1. **Local System DB:** High-clearance database entries checked via secure `bcrypt` hashing algorithms.
2. **Active Directory / LDAP:** Native simple bind handshakes processed directly against corporate Domain Controllers.
3. **RADIUS Server Framework:** Authentication verification via standard `Access-Request` challenge packets.

### Exchanging Credentials for Access Tokens:
To authenticate, users must submit their credentials via the centralized `/login` UI page, which performs a form POST to the token gateway:

```bash
curl -X POST "http://127.0.0" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=net_admin&password=VaultSecuredPassword123!"
```

**Expected JSON Response Body:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "role": "admin"
}
```
*Note: The user interface automatically captures this token on successful login and stores it inside the browser's `localStorage` as `nornir_access_token`. This token is parsed dynamically and passed securely via URL query string parameters for real-time WebSocket log authorization.*

## 📂 2. GitLab Project Management & Source Control Sync
Automation code is organized into isolated, source-controlled "Projects" instead of flat local server scripts. To update or clone an orchestration repository onto the server workspace, run a synchronized POST request:

```bash
curl -X POST "http://127.0.0" \
     -H "Authorization: Bearer <your_access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "repo_url": "https://yourdomain.local",
       "branch": "main",
       "gitlab_token": "glpat-YourPersonalAccessToken123"
     }'
```
*Security Guard: This endpoint is restricted at an object level via granular RBAC rules. Users must hold an explicit `write` action permission mapping directly to project ID `100` to alter code states.*

---

## ⚡ 3. Granular Object-Level Job Execution
The platform enforces precise **Object-Level RBAC**. Users are assigned to structural Groups which are mapped to explicit objects (Projects, Inventories, Credentials) and specific actions (`read`, `execute`, `write`). Global role defaults no more override resource constraints.

To execute a validated automation script out of a specific GitLab sync folder, trigger the project execution endpoint:

```bash
curl -X POST "http://127.0.0" \
     -H "Authorization: Bearer <your_access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "job_type": "deploy_ntp",
       "netbox_filters": {
         "site": "dfw",
         "role": "backbone-switch"
       },
       "extra_vars": {
         "configs": ["ntp server 10.10.10.1 prefer"]
       }
     }'
```

---

## 📊 4. Interactive Single-Page HTMX Interface
Navigating to `http://<server_ip>:8000/jobs/<job_id>` opens a unified HTML5/CSS3 terminal monitoring dashboard. The front-end leverages native HTMX layout attributes to load panels seamlessly without complete browser reloads:
- **Token-Secured Live Log Streaming:** The interface reads the active access token from browser storage and passes it down the WebSocket connection query line (`?token=<jwt_string>`). FastAPI intercepts this instantly, verifying active permission parameters before channeling live standard output streams from **Percona Valkey**.
- **Dynamic Content Viewports:** Clicking the header navigation links (`[Schedules]`, `[Inventories]`, `[Projects]`) prompts HTMX to execute an asynchronous asynchronous GET request to FastAPI. The backend returns clean, partial HTML pane elements that overwrite the `#main-content-viewport` container instantly without disrupting active console output streams or status widgets.
- **Routine Automation Schedules:** Automated timelines are managed directly from the workspace view component pane backed by an asynchronous **APScheduler** execution engine layer. Routine configurations, targeted fields, and crontab loops are written directly to PostgreSQL tables and pushed down the **ZeroMQ pipeline** instantly when intervals hit zero.

