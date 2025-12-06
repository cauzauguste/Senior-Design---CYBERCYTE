# CYBERCYTE FastAPI Backend - Deployment Summary

## System Architecture

Three VMs working together:

| VM | IP Address | Role | Port |
|---|---|---|---|
| **Postgres DB** | `34.132.194.35` | Central database (PostgreSQL) | `5432` |
| **Backend FastAPI** | `136.114.77.42` | FastAPI REST API server | `8000` |
| **Zeek Sender** | `35.222.249.202` | Zeek IDS logs → Postgres | Various |

---

## ✅ Current Status

### Connectivity Tests Passed
- ✅ Postgres VM reachable at `34.132.194.35:5432`
- ✅ Backend VM FastAPI reachable at `136.114.77.42:8000`
- ✅ Backend VM SSH reachable at `136.114.77.42:22`
- ✅ Zeek VM SSH reachable at `35.222.249.202:22`
- ⚠️  Zeek VM → Postgres (`35.222.249.202:5432`) — network restricted (see fix below)

### Database Status
- ✅ Postgres accepting connections with password: `pass`
- ✅ Tables exist: `zeek_conn`, `zeek_conn_logs`
- ✅ Database: `cybercyte_db`

### FastAPI Status
- ✅ FastAPI backend running and responsive
- ✅ `/health` endpoint returns `{"status": "ok"}`
- ✅ DB startup hooks added (test connectivity on startup)
- ✅ All Python dependencies installed and working

---

## 🚀 Deployment Instructions

### 1. On Backend VM (`136.114.77.42`)

#### Step 1.1: SSH into the backend VM
```bash
ssh your-user@136.114.77.42
```

#### Step 1.2: Navigate to the project and set up Python environment
```bash
cd /home/zauguste52/Senior-Design---CYBERCYTE

# Create and activate virtual environment (if not already done)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --break-system-packages -r requirements.txt
pip install scapy python-multipart  # Additional dependencies
```

#### Step 1.3: Export environment variables and start FastAPI
```bash
export POSTGRES_URL='postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db'
export DATABASE_URL="$POSTGRES_URL"

# Run FastAPI
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

#### Step 1.4: Verify connectivity (from another terminal on same VM or remote)
```bash
# Test health endpoint
curl http://136.114.77.42:8000/health
# Expected: {"status":"ok"}

# Check other endpoints
curl http://136.114.77.42:8000/docs  # Swagger UI
```

#### Step 1.5 (Optional): Run as a systemd service
Create `/etc/systemd/system/cybercyte-backend.service`:
```ini
[Unit]
Description=Cybercyte FastAPI Backend
After=network.target

[Service]
Type=simple
User=zauguste52
WorkingDirectory=/home/zauguste52/Senior-Design---CYBERCYTE
Environment="POSTGRES_URL=postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db"
Environment="DATABASE_URL=postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db"
ExecStart=/home/zauguste52/Senior-Design---CYBERCYTE/venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cybercyte-backend
sudo systemctl start cybercyte-backend
sudo systemctl status cybercyte-backend
```

---

### 2. On Zeek Sender VM (`35.222.249.202`)

#### Step 2.1: SSH into the Zeek VM
```bash
ssh your-user@35.222.249.202
```

#### Step 2.2: Copy the backend project (or ensure it's available)
```bash
# If not already present
git clone https://github.com/cauzauguste/Senior-Design---CYBERCYTE.git /opt/cybercyte
cd /opt/cybercyte
```

#### Step 2.3: Set up Python environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --break-system-packages -r requirements.txt
pip install asyncpg paramiko  # Additional for zeek reader
```

#### Step 2.4: Configure Zeek log reader environment
Edit or create `backend/app/.env.zeek_reader`:
```bash
export ZEEK_LOG_DIR=/opt/zeek/logs/current
export ZEEK_PROCESSED_DIR=/opt/zeek/logs/processed
export ZEEK_POLL_INTERVAL=10
export POSTGRES_URL='postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db'
export LOG_LEVEL=INFO
```

#### Step 2.5: Run the Zeek log reader
```bash
source venv/bin/activate
export POSTGRES_URL='postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db'

python3 backend/app/zeek_log_reader.py
```

Expected output:
```
INFO - Starting Zeek log monitor on directory: /opt/zeek/logs/current
INFO - PostgreSQL connection pool initialized
INFO - Zeek tables created/verified
```

#### Step 2.6 (Optional): Run as a systemd service
Create `/etc/systemd/system/cybercyte-zeek-reader.service`:
```ini
[Unit]
Description=Cybercyte Zeek Log Reader
After=network.target

[Service]
Type=simple
User=zauguste52
WorkingDirectory=/opt/cybercyte
Environment="POSTGRES_URL=postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db"
Environment="ZEEK_LOG_DIR=/opt/zeek/logs/current"
Environment="ZEEK_PROCESSED_DIR=/opt/zeek/logs/processed"
Environment="ZEEK_POLL_INTERVAL=10"
ExecStart=/opt/cybercyte/venv/bin/python3 backend/app/zeek_log_reader.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cybercyte-zeek-reader
sudo systemctl start cybercyte-zeek-reader
sudo systemctl status cybercyte-zeek-reader
```

---

## 🔧 Troubleshooting

### Issue: Connection to Postgres VM times out from Zeek VM

**Problem:** `35.222.249.202:5432` → `34.132.194.35` timed out

**Solutions:**

1. **Check network connectivity from Zeek VM:**
   ```bash
   ssh your-user@35.222.249.202
   nc -vz 34.132.194.35 5432
   # or
   telnet 34.132.194.35 5432
   ```

2. **Check outbound firewall rules on Zeek VM:**
   ```bash
   sudo ufw status
   sudo iptables -L -n
   ```

3. **Ensure Postgres VM allows connections from Zeek VM:**
   On Postgres VM (`34.132.194.35`):
   ```bash
   sudo nano /etc/postgresql/*/main/pg_hba.conf
   # Add or verify:
   # host    cybercyte_db    postgres    35.222.249.202/32    md5
   
   sudo systemctl reload postgresql
   ```

4. **Check GCP/Cloud Security Groups:**
   - Ensure firewall rule allows TCP port `5432` from `35.222.249.202` to `34.132.194.35`

---

## 📝 Configuration Files

### `.env` (Backend)
Location: `backend/app/.env`
```dotenv
DB_BACKEND=postgres
POSTGRES_HOST=34.132.194.35
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=pass
POSTGRES_DB=cybercyte_db
POSTGRES_URL=postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db
DATABASE_URL=postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db
```

### `.env.zeek_reader` (Zeek Sender)
Location: `backend/app/.env.zeek_reader`
```dotenv
ZEEK_LOG_DIR=/opt/zeek/logs/current
ZEEK_PROCESSED_DIR=/opt/zeek/logs/processed
ZEEK_POLL_INTERVAL=10
POSTGRES_URL=postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db
```

---

## 📊 Verification Checklist

After deployment, verify:

- [ ] Backend FastAPI is running and responding to `/health`
- [ ] Zeek log reader is running and connected to Postgres
- [ ] Logs from Zeek appear in `zeek_events` table in Postgres
- [ ] Postgres VM is accessible from both VMs on port `5432`
- [ ] Environment variables are exported in each service startup script
- [ ] Systemd services (if deployed) are enabled and auto-starting

---

## 🔐 Security Notes

- **Password is in plaintext** — For production, use:
  - Postgres connection with SSL/TLS
  - `.pgpass` file for credential management
  - Environment variable injection from a secrets manager (AWS Secrets Manager, Vault, etc.)
  - Restricting IP ranges in `pg_hba.conf`

- **Firewall rules** — Ensure:
  - Postgres port only accessible from known IPs
  - FastAPI port only accessible from authorized clients
  - Outbound rules allow Zeek VM to reach Postgres

---

## 📚 Related Documentation

- `QUICK_START.md` — Quick setup guide
- `DEPLOYMENT_GUIDE.md` — Original deployment notes
- `ZEEK_README.md` — Zeek-specific setup
- `ZEEK_SETUP_GUIDE.md` — Zeek IDS configuration

---

Generated: December 5, 2025
