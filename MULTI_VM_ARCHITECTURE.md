# Multi-VM Data Flow Summary

## Your Setup

```
┌─────────────────────────────────────────────────────────────────────┐
│  CYBERCYTE THREE-VM ARCHITECTURE (December 5, 2025)                │
└─────────────────────────────────────────────────────────────────────┘

    VM 1: ZEEK SENSOR
    IP: 35.222.249.202
    ┌──────────────────────────────┐
    │  Network packet capture      │
    │  & security event logging    │
    │                              │
    │  /opt/zeek/logs/current:     │
    │  • conn.log                  │
    │  • dns.log                   │
    │  • http.log                  │
    │  • ssl.log                   │
    │  • files.log                 │
    │                              │
    │  Exposed via SSH/SFTP (22)   │
    └──────────────┬───────────────┘
                   │ SFTP Download
                   │ SSH Tunnel
                   │
    ┌──────────────▼───────────────┐
    │  VM 2: FASTAPI BACKEND       │ ◄─── YOU ARE HERE
    │  IP: 34.170.121.14           │
    │                              │
    │  FastAPI (Port 8000)         │
    │  ├─ NEW: zeek_remote_client  │
    │  │   • Connects to Zeek VM   │
    │  │   • Retrieves logs        │
    │  │   • Parses events         │
    │  │                           │
    │  ├─ NEW: routes/zeek_remote  │
    │  │   • /zeek/remote/health   │
    │  │   • /zeek/remote/list     │
    │  │   • /zeek/remote/ingest   │
    │  │                           │
    │  └─ PostgresIngester         │
    │      • Parse JSON            │
    │      • Batch insert          │
    │                              │
    └──────────────┬───────────────┘
                   │ PostgreSQL Protocol
                   │ TCP/5432
                   │ asyncpg
                   │
    ┌──────────────▼───────────────┐
    │  VM 3: DATABASE              │
    │  IP: 34.132.194.35           │
    │                              │
    │  PostgreSQL 15               │
    │  ├─ zeek_events              │
    │  ├─ zeek_connections         │
    │  ├─ zeek_dns                 │
    │  ├─ zeek_http                │
    │  ├─ zeek_ssl                 │
    │  └─ zeek_files               │
    │                              │
    │  Storage for all events      │
    │  & historical data           │
    └──────────────────────────────┘
```

---

## Data Flow Steps

### STEP 1: FastAPI connects to Zeek VM

```python
from backend.app.zeek_remote_client import ZeekRemoteClient

client = ZeekRemoteClient(
    host="35.222.249.202",      # Zeek VM
    port=22,                     # SSH port
    username="zauguste52",       # SSH username
    remote_path="/opt/zeek/logs/current"
)

await client.connect()  # Establishes SFTP connection
```

**Protocol**: SSH/SFTP (encrypted, read-only)

---

### STEP 2: FastAPI lists available logs

```python
files = await client.list_log_files()
# Returns: ['conn.log', 'dns.log', 'http.log', 'ssl.log', 'files.log']
```

**Location**: `/opt/zeek/logs/current/` on Zeek VM (35.222.249.202)

---

### STEP 3: FastAPI downloads log file

```python
log_content = await client.get_log_content('conn.log')
# Returns: String with entire JSON-formatted log file
```

**Format**: One JSON object per line (Zeek JSON format)

Example lines:
```json
{"ts":1701753600.1,"uid":"CAqnQK4fake1abc","id.orig_h":"192.168.1.100","id.orig_p":54321,"id.resp_h":"8.8.8.8","id.resp_p":53,...}
{"ts":1701753601.2,"uid":"CAqnQK4fake2def","id.orig_h":"192.168.1.101","id.orig_p":54322,"id.resp_h":"8.8.8.9","id.resp_p":443,...}
```

---

### STEP 4: FastAPI parses JSON events

```python
from backend.app.zeek_remote_client import PostgresIngester

ingester = PostgresIngester(
    db_url="postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db"
)

# Parse and insert
lines_processed, lines_inserted = await ingester.parse_and_ingest_log_content(
    log_content,
    'conn.log'
)
```

**Processing**: 
- Skips header lines (starting with #)
- Parses each line as JSON
- Routes to appropriate table based on log type

---

### STEP 5: FastAPI inserts into PostgreSQL

```sql
-- Example: conn.log insertion
INSERT INTO zeek_connections (
    uid, source_ip, dest_ip, source_port, dest_port, 
    protocol, duration, bytes_sent, bytes_received, 
    connection_state, raw_data
) VALUES (
    'CAqnQK4fake1abc', 
    '192.168.1.100'::inet, 
    '8.8.8.8'::inet,
    54321,
    53,
    'udp',
    '0.5 seconds',
    128,
    256,
    'SF',
    '{...full JSON...}'::jsonb
);
```

**Target**: PostgreSQL VM (34.132.194.35:5432)

---

## API Endpoints (NEW)

All endpoints run on `http://34.170.121.14:8000`

### Test Connectivity
```
GET /zeek/remote/health
```
Response: Shows Zeek VM & PostgreSQL VM status

### List Remote Logs
```
GET /zeek/remote/list-logs
```
Response: Lists all .log files on Zeek VM

### Ingest Single Log
```
GET /zeek/remote/ingest-log?filename=conn.log
```
Response: Shows how many events were inserted

### Bulk Ingest All Logs
```
POST /zeek/remote/ingest-all
```
Response: Starts background ingestion of all logs

### Full Diagnostics
```
GET /zeek/remote/test-connection
```
Response: Detailed connectivity info for each VM

---

## Quick Command Reference

### 1. Check if everything is connected
```bash
curl http://34.170.121.14:8000/zeek/remote/health
```

### 2. See what logs are available on Zeek VM
```bash
curl http://34.170.121.14:8000/zeek/remote/list-logs
```

### 3. Pull connection logs and store in PostgreSQL
```bash
curl "http://34.170.121.14:8000/zeek/remote/ingest-log?filename=conn.log"
```

### 4. Pull ALL logs at once
```bash
curl -X POST http://34.170.121.14:8000/zeek/remote/ingest-all
```

### 5. Run full connectivity test
```bash
python3 test_connectivity.py
```

### 6. Query what was stored
```bash
psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db

# Then in psql:
SELECT COUNT(*) FROM zeek_connections;
SELECT * FROM zeek_dns LIMIT 5;
```

---

## Files Added

```
backend/app/
├─ zeek_remote_client.py       ← NEW: SFTP + PostgreSQL client
└─ routes/
   └─ zeek_remote.py            ← NEW: 5 new API endpoints

test_connectivity.py             ← NEW: Full diagnostic script

ZEEK_REMOTE_INTEGRATION.md       ← NEW: Detailed architecture docs
FASTAPI_REMOTE_SETUP.md          ← NEW: Setup & usage guide
MULTI_VM_ARCHITECTURE.md         ← NEW: This file
```

---

## Environment Variables Needed

```bash
# .env file in project root

# Zeek VM (35.222.249.202)
ZEEK_REMOTE_HOST=35.222.249.202
ZEEK_REMOTE_PORT=22
ZEEK_REMOTE_USER=zauguste52
ZEEK_REMOTE_PATH=/opt/zeek/logs/current
ZEEK_SSH_KEY=/path/to/ssh/key  # or ZEEK_SSH_PASSWORD

# PostgreSQL VM (34.132.194.35)
POSTGRES_URL=postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db
```

---

## How to Use

### For First Time Setup

```bash
# 1. Navigate to project
cd /home/zauguste52/Senior-Design---CYBERCYTE

# 2. Test everything is connected
python3 test_connectivity.py

# 3. Start FastAPI
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# 4. In another terminal, pull logs
curl "http://34.170.121.14:8000/zeek/remote/ingest-log?filename=conn.log"

# 5. Check they're in PostgreSQL
psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db -c \
  "SELECT COUNT(*) FROM zeek_connections;"
```

---

## Key Technology Components

| Component | Purpose | Technology |
|-----------|---------|-----------|
| **Zeek VM** | Packet capture & IDS | Zeek IDS (35.222.249.202) |
| **FastAPI** | Orchestration & API | Python 3.12 + FastAPI (34.170.121.14) |
| **SFTP Client** | Remote log access | Paramiko (SSH/SFTP) |
| **Log Parser** | Event extraction | Python + JSON |
| **Database Client** | PostgreSQL ops | asyncpg (async) |
| **Storage** | Event persistence | PostgreSQL 15 (34.132.194.35) |

---

## Data Flow Timing

```
Zeek VM writes log  →  FastAPI polls every N sec  →  FastAPI downloads
     (real-time)              (configurable)         (SFTP)
                                    ↓
                           Parse JSON events
                                    ↓
                         Insert to PostgreSQL
                              (batched)
```

---

## What's Happening

When you run the new endpoints:

1. **FastAPI** (on 34.170.121.14) initiates SSH connection to **Zeek VM** (35.222.249.202)
2. **FastAPI** downloads the log file via SFTP
3. **FastAPI** parses the JSON format log into Python dictionaries
4. **FastAPI** connects to **PostgreSQL** (on 34.132.194.35)
5. **FastAPI** inserts parsed events into appropriate table
6. **PostgreSQL** stores the data with full schema/indexes
7. You can now query the data with SQL or via FastAPI endpoints

---

## Summary

- ✅ **Zeek VM (35.222.249.202)**: Generates logs via SSH/SFTP
- ✅ **FastAPI VM (34.170.121.14)**: Retrieves & ingests logs
- ✅ **PostgreSQL VM (34.132.194.35)**: Stores centralized events

Data flows: **Zeek VM → FastAPI VM → PostgreSQL VM**

---

*Setup complete! You now have a scalable architecture for collecting, parsing, and storing Zeek security events.*
