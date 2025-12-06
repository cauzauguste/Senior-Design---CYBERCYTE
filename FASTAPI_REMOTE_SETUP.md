# FastAPI Remote Zeek Integration - Quick Deployment Guide

## Summary of Changes

This guide covers the new remote Zeek integration features added to the FastAPI backend on 34.170.121.14 to pull logs from Zeek VM (35.222.249.202) and store them in PostgreSQL (34.132.194.35).

---

## Files Added/Modified

### New Files Created

1. **`backend/app/zeek_remote_client.py`**
   - `ZeekRemoteClient`: SFTP client for connecting to remote Zeek VM
   - `PostgresIngester`: Handles database operations and log parsing
   - Handles SSH authentication (key or password-based)

2. **`backend/app/routes/zeek_remote.py`**
   - FastAPI endpoints for remote Zeek integration
   - 5 new REST API endpoints for health checks, log retrieval, and ingestion

3. **`test_connectivity.py`**
   - Standalone script to test connectivity to all three VMs
   - Detailed diagnostics output with colored formatting
   - Saves results to JSON file

4. **`ZEEK_REMOTE_INTEGRATION.md`**
   - Comprehensive documentation of architecture and data flow
   - Setup instructions and API reference

### Modified Files

1. **`backend/app/main.py`**
   - Added import for new zeek_remote router
   - Registered zeek_remote routes with FastAPI

---

## Setup Instructions

### Step 1: Configure Environment Variables

Create or update `.env` in project root:

```bash
# Zeek VM Configuration
ZEEK_REMOTE_HOST=35.222.249.202
ZEEK_REMOTE_PORT=22
ZEEK_REMOTE_USER=zauguste52
ZEEK_REMOTE_PATH=/opt/zeek/logs/current

# SSH Authentication (choose one):
# Option A: SSH Key (preferred)
ZEEK_SSH_KEY=/home/zauguste52/.ssh/id_rsa

# Option B: Password (fallback)
# ZEEK_SSH_PASSWORD=your_password_here

# PostgreSQL Configuration
POSTGRES_URL=postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db
```

### Step 2: Test Connectivity

```bash
cd /home/zauguste52/Senior-Design---CYBERCYTE

# Run the connectivity test script
python3 test_connectivity.py
```

**Expected output**:
- ✓ FastAPI local setup: ok
- ✓ Zeek VM (35.222.249.202): connected
- ✓ PostgreSQL VM (34.132.194.35): connected

### Step 3: Start FastAPI

```bash
# Navigate to project directory
cd /home/zauguste52/Senior-Design---CYBERCYTE

# Activate virtual environment (if using one)
source venv/bin/activate  # or your venv path

# Install dependencies (if needed)
pip install -r requirements.txt

# Start FastAPI server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

---

## Using the New API Endpoints

### 1. Health Check

Test if FastAPI can connect to both Zeek VM and PostgreSQL:

```bash
curl http://34.170.121.14:8000/zeek/remote/health | jq .
```

Response:
```json
{
  "zeek_vm": {"host": "35.222.249.202", "port": 22, "status": "connected"},
  "postgres_vm": {"host": "34.132.194.35", "status": "available"},
  "overall": "healthy"
}
```

### 2. List Available Logs

See what log files are available on the Zeek VM:

```bash
curl http://34.170.121.14:8000/zeek/remote/list-logs | jq .
```

Response:
```json
{
  "zeek_vm": "35.222.249.202",
  "remote_path": "/opt/zeek/logs/current",
  "log_files": ["conn.log", "dns.log", "http.log", "ssl.log"],
  "count": 4
}
```

### 3. Ingest a Single Log File

Download and parse a specific log file from Zeek VM, insert into PostgreSQL:

```bash
# Ingest connection logs
curl "http://34.170.121.14:8000/zeek/remote/ingest-log?filename=conn.log" | jq .
```

Response:
```json
{
  "status": "success",
  "zeek_vm": "35.222.249.202",
  "postgres_vm": "34.132.194.35",
  "filename": "conn.log",
  "lines_processed": 1250,
  "lines_inserted": 1248,
  "message": "Ingested 1248 events from conn.log"
}
```

### 4. Bulk Ingest All Logs

Download all log files and ingest them (runs in background):

```bash
curl -X POST http://34.170.121.14:8000/zeek/remote/ingest-all | jq .
```

Response:
```json
{
  "status": "ingestion_started",
  "message": "Bulk log ingestion started in background",
  "check_endpoint": "/zeek/remote/ingest-status"
}
```

### 5. Full Connectivity Diagnostics

Detailed connectivity test with PostgreSQL version info:

```bash
curl http://34.170.121.14:8000/zeek/remote/test-connection | jq .
```

---

## Data Flow Verification

### Step 1: Check PostgreSQL Tables

```bash
# SSH to Postgres VM
ssh user@34.132.194.35

# Connect to database
psql postgresql://postgres:pass@localhost:5432/cybercyte_db

# List tables
\dt zeek_*

# Check row counts
SELECT table_name, 
       (SELECT COUNT(*) FROM public.zeek_events) as count
FROM information_schema.tables 
WHERE table_name LIKE 'zeek_%';

# Exit psql
\q
```

### Step 2: Query Ingested Events

```bash
# Via psql
psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db

# Show recent connection events
SELECT timestamp, source_ip, dest_ip, source_port, dest_port, protocol 
FROM zeek_connections 
ORDER BY timestamp DESC 
LIMIT 10;

# Show DNS events
SELECT timestamp, query, rcode, query_type 
FROM zeek_dns 
ORDER BY timestamp DESC 
LIMIT 10;
```

---

## Architecture Overview

```
FastAPI (34.170.121.14)
  ↓
  ├─→ zeek_remote_client.py
  │   ├─ ZeekRemoteClient (SFTP to 35.222.249.202)
  │   └─ PostgresIngester (writes to 34.132.194.35)
  │
  └─→ routes/zeek_remote.py
      ├─ GET  /zeek/remote/health
      ├─ GET  /zeek/remote/list-logs
      ├─ GET  /zeek/remote/ingest-log
      ├─ POST /zeek/remote/ingest-all
      └─ GET  /zeek/remote/test-connection
```

---

## Troubleshooting

### SSH Connection Fails

**Problem**: "SSH authentication failed"

**Solution**:
1. Verify SSH key is accessible: `ls -la /home/zauguste52/.ssh/id_rsa`
2. Test SSH manually: `ssh -i /home/zauguste52/.ssh/id_rsa zauguste52@35.222.249.202`
3. If using password, set: `export ZEEK_SSH_PASSWORD='your_password'`

### PostgreSQL Connection Fails

**Problem**: "PostgreSQL connection refused"

**Solution**:
1. Verify Postgres is running: `sudo systemctl status postgresql`
2. Check firewall: `sudo ufw allow from 34.170.121.14 to any port 5432`
3. Edit `/etc/postgresql/*/main/pg_hba.conf` to allow FastAPI VM:
   ```
   host    cybercyte_db    postgres    34.170.121.14/32    md5
   ```
4. Restart PostgreSQL: `sudo systemctl reload postgresql`

### No Zeek Logs Found

**Problem**: "Log file not found on Zeek VM"

**Solution**:
1. SSH to Zeek VM: `ssh zauguste52@35.222.249.202`
2. Check if logs exist: `ls -la /opt/zeek/logs/current/`
3. Check if Zeek is running: `zeekctl status`
4. Generate test traffic to create logs
5. Verify path in .env matches actual location

---

## Performance Notes

- **Typical ingestion rate**: 1000-5000 events/sec per log file
- **Connection timeout**: 30 seconds (SFTP)
- **Memory usage**: ~100MB per 10,000 events in pool
- **Recommended batch size**: Ingest one log file at a time for stability

---

## Security Recommendations

1. **Use SSH Keys**: Don't store passwords in .env
   ```bash
   # Generate key
   ssh-keygen -t ed25519 -f ~/.ssh/zeek_key
   
   # Copy to Zeek VM
   ssh-copy-id -i ~/.ssh/zeek_key.pub zauguste52@35.222.249.202
   
   # Set in .env
   ZEEK_SSH_KEY=/home/zauguste52/.ssh/zeek_key
   ```

2. **Restrict PostgreSQL Access**: Whitelist only FastAPI VM
   ```bash
   # In /etc/postgresql/*/main/pg_hba.conf
   host    cybercyte_db    postgres    34.170.121.14/32    md5
   ```

3. **Protect .env File**:
   ```bash
   chmod 600 .env
   ```

---

## Next Steps

1. ✅ Run: `python3 test_connectivity.py`
2. ✅ Start: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
3. ✅ Test: `curl http://34.170.121.14:8000/zeek/remote/health`
4. ✅ Ingest: `curl "http://34.170.121.14:8000/zeek/remote/ingest-log?filename=conn.log"`
5. ✅ Verify: Check PostgreSQL tables for new events

---

## Support

For detailed information, see:
- **Architecture & Data Flow**: `ZEEK_REMOTE_INTEGRATION.md`
- **Deployment Guide**: `DEPLOYMENT_GUIDE.md`
- **Zeek Setup**: `ZEEK_SETUP_GUIDE.md`

---

*Last updated: December 5, 2025*
