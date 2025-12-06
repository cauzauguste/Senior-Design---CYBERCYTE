# Cybercyte Remote Zeek Integration - Data Flow Documentation

## Overview

This document explains how FastAPI on VM 34.170.121.14 connects to the Zeek sensor on 35.222.249.202, retrieves logs, and sends them to PostgreSQL on 34.132.194.35.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CYBERCYTE MULTI-VM ARCHITECTURE                     │
└─────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────┐
    │  Zeek Sensor VM      │
    │  35.222.249.202      │
    │                      │
    │  ┌────────────────┐  │
    │  │  /opt/zeek/    │  │
    │  │  logs/current/ │  │
    │  │                │  │
    │  │  • conn.log    │  │
    │  │  • dns.log     │  │
    │  │  • http.log    │  │
    │  │  • ssl.log     │  │
    │  │  • files.log   │  │
    │  └────────────────┘  │
    │                      │
    │  SSH/SFTP (port 22)  │
    └──────────┬───────────┘
               │
               │ SFTP Protocol
               │ Read-only access
               │
               ↓
    ┌──────────────────────────────────────────┐
    │      FastAPI VM (Backend)                │
    │      34.170.121.14                       │
    │                                          │
    │  ┌────────────────────────────────────┐  │
    │  │     FastAPI (Port 8000)            │  │
    │  │                                    │  │
    │  │  New Routes:                       │  │
    │  │  • /zeek/remote/health             │  │
    │  │  • /zeek/remote/list-logs          │  │
    │  │  • /zeek/remote/ingest-log         │  │
    │  │  • /zeek/remote/ingest-all         │  │
    │  │  • /zeek/remote/test-connection    │  │
    │  │                                    │  │
    │  │  zeek_remote_client.py:            │  │
    │  │  • ZeekRemoteClient (SFTP)         │  │
    │  │  • PostgresIngester                │  │
    │  └────────────────────────────────────┘  │
    │                                          │
    │  Functions:                              │
    │  • Connect to remote Zeek via SFTP       │
    │  • Parse Zeek JSON logs                  │
    │  • Insert into PostgreSQL                │
    └──────────┬───────────────────────────────┘
               │
               │ PostgreSQL Protocol (TCP/5432)
               │ asyncpg connection pool
               │
               ↓
    ┌──────────────────────────────────────────┐
    │      PostgreSQL VM (Database)            │
    │      34.132.194.35                       │
    │                                          │
    │  ┌────────────────────────────────────┐  │
    │  │    PostgreSQL 15 (Port 5432)       │  │
    │  │                                    │  │
    │  │  Zeek Tables:                      │  │
    │  │  • zeek_events (generic)           │  │
    │  │  • zeek_connections (conn.log)     │  │
    │  │  • zeek_dns (dns.log)              │  │
    │  │  • zeek_files (files.log)          │  │
    │  │  • zeek_http (http.log)            │  │
    │  │  • zeek_ssl (ssl.log)              │  │
    │  │                                    │  │
    │  │  Indexes on:                       │  │
    │  │  • timestamp                       │  │
    │  │  • source_ip, dest_ip              │  │
    │  │  • log_type                        │  │
    │  │                                    │  │
    │  └────────────────────────────────────┘  │
    │                                          │
    └──────────────────────────────────────────┘
```

---

## Data Flow Steps

### Step 1: FastAPI → Zeek VM (SSH/SFTP Connection)

**Component**: `ZeekRemoteClient` class

```python
# Connection
client = ZeekRemoteClient(
    host="35.222.249.202",
    port=22,
    username="zauguste52",
    remote_path="/opt/zeek/logs/current",
    ssh_key="/path/to/key"  # or use password
)

await client.connect()  # Establishes SFTP channel
```

**Authentication Options**:
- SSH Key-based (preferred)
  - Set `ZEEK_SSH_KEY` environment variable
- Password-based (fallback)
  - Set `ZEEK_SSH_PASSWORD` environment variable

**Security Notes**:
- SFTP operates over SSH (encrypted)
- Read-only file access
- Can list and download log files

---

### Step 2: FastAPI Retrieves Zeek Logs

**Component**: `ZeekRemoteClient.get_log_content()`

```python
# Get list of available logs
files = await client.list_log_files()
# Returns: ['conn.log', 'dns.log', 'http.log', ...]

# Download specific log file
content = await client.get_log_content('conn.log')
# Returns: String containing entire log file contents
```

**Format**: Zeek logs in JSON format (one JSON object per line)

Example log line:
```json
{"ts":1701753600,"uid":"CAqnQK1234abc","id.orig_h":"192.168.1.100","id.orig_p":54321,"id.resp_h":"8.8.8.8","id.resp_p":53,"proto":"udp","service":"dns",...}
```

---

### Step 3: FastAPI Parses Logs

**Component**: `PostgresIngester.parse_zeek_json_line()`

```python
# Parse each line of the log file
for line in log_content.split('\n'):
    if line and not line.startswith('#'):
        parsed_data = json.loads(line)
        # parsed_data is now a Python dict
```

**Handling Different Log Types**:
- `conn.log` → Insert to `zeek_connections` table
- `dns.log` → Insert to `zeek_dns` table
- `http.log` → Insert to `zeek_http` table
- `ssl.log` → Insert to `zeek_ssl` table
- Other → Insert to `zeek_events` table

---

### Step 4: FastAPI Writes to PostgreSQL

**Component**: `PostgresIngester` class

```python
# Initialize pool
ingester = PostgresIngester(
    db_url="postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db"
)
await ingester.init_pool()

# Ensure tables exist
await ingester.ensure_tables()

# Insert events
for log_line in parsed_logs:
    if log_type == 'conn.log':
        await ingester.insert_connection(parsed_data)
    elif log_type == 'dns.log':
        await ingester.insert_dns_event(parsed_data)
    else:
        await ingester.insert_zeek_event(parsed_data)
```

**Database Schema**:
```sql
-- Example: zeek_connections table
CREATE TABLE zeek_connections (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    uid VARCHAR(50),
    source_ip INET NOT NULL,
    dest_ip INET NOT NULL,
    source_port INTEGER NOT NULL,
    dest_port INTEGER NOT NULL,
    protocol VARCHAR(10) NOT NULL,
    duration INTERVAL,
    bytes_sent BIGINT DEFAULT 0,
    bytes_received BIGINT DEFAULT 0,
    connection_state VARCHAR(20),
    raw_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## API Endpoints

All endpoints are part of the Zeek Remote Integration routes in FastAPI:

### 1. Health Check - Test All Connections

```bash
GET /zeek/remote/health
```

**Response**:
```json
{
  "zeek_vm": {
    "host": "35.222.249.202",
    "port": 22,
    "status": "connected"
  },
  "postgres_vm": {
    "host": "34.132.194.35",
    "status": "available"
  },
  "overall": "healthy"
}
```

---

### 2. List Remote Log Files

```bash
GET /zeek/remote/list-logs
```

**Response**:
```json
{
  "zeek_vm": "35.222.249.202",
  "remote_path": "/opt/zeek/logs/current",
  "log_files": ["conn.log", "dns.log", "http.log", "ssl.log"],
  "count": 4
}
```

---

### 3. Ingest Single Log File

```bash
GET /zeek/remote/ingest-log?filename=conn.log
```

**Process**:
1. Connect to Zeek VM (35.222.249.202)
2. Download `conn.log` from `/opt/zeek/logs/current/`
3. Parse JSON lines
4. Insert into PostgreSQL on 34.132.194.35
5. Return statistics

**Response**:
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

---

### 4. Bulk Ingest All Logs

```bash
POST /zeek/remote/ingest-all
```

**Process** (runs in background):
1. Connect to Zeek VM
2. List all `.log` files
3. For each file:
   - Download
   - Parse
   - Insert into PostgreSQL
4. Returns immediately with task ID

**Response**:
```json
{
  "status": "ingestion_started",
  "message": "Bulk log ingestion started in background",
  "check_endpoint": "/zeek/remote/ingest-status"
}
```

---

### 5. Test Full Connectivity

```bash
GET /zeek/remote/test-connection
```

**Response**:
```json
{
  "zeek_vm": {
    "host": "35.222.249.202",
    "port": 22,
    "username": "zauguste52",
    "remote_path": "/opt/zeek/logs/current"
  },
  "postgres_vm": {
    "url": "postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db"
  },
  "connectivity": {
    "zeek_vm": {
      "status": "connected",
      "log_files_found": 4,
      "sample_files": ["conn.log", "dns.log", "http.log", "ssl.log"]
    },
    "postgres_vm": {
      "status": "connected",
      "version": "PostgreSQL 15.5 on x86_64-pc-linux-gnu..."
    }
  }
}
```

---

## Environment Variables

Create a `.env` file in the project root:

```bash
# ============================================================================
# ZEEK VM CONFIGURATION (35.222.249.202)
# ============================================================================
ZEEK_REMOTE_HOST=35.222.249.202
ZEEK_REMOTE_PORT=22
ZEEK_REMOTE_USER=zauguste52
ZEEK_REMOTE_PATH=/opt/zeek/logs/current

# SSH Authentication - Choose ONE:
# Option 1: SSH Key (Preferred)
ZEEK_SSH_KEY=/path/to/private/key

# Option 2: Password (Fallback)
# ZEEK_SSH_PASSWORD=your_password_here

# ============================================================================
# POSTGRESQL VM CONFIGURATION (34.132.194.35)
# ============================================================================
POSTGRES_URL=postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db

# Optional: CA certificate for SSL connections
# POSTGRES_CA_FILE=/path/to/ca-cert.pem

# ============================================================================
# FASTAPI CONFIGURATION
# ============================================================================
# This FastAPI instance
FASTAPI_HOST=34.170.121.14
FASTAPI_PORT=8000
```

---

## Testing Connectivity

### Run the Comprehensive Test Script

```bash
cd /home/zauguste52/Senior-Design---CYBERCYTE

# Install dependencies (if not already)
pip install -r requirements.txt

# Run connectivity tests
python3 test_connectivity.py
```

**Output**:
```
======================================================================
                 CYBERCYTE VM CONNECTIVITY DIAGNOSTIC
======================================================================

Testing FastAPI local setup...
✓ paramiko installed
✓ asyncpg installed
...

Testing Zeek VM SSH Connection...
✓ SSH authentication successful
✓ Remote path accessible
Found 4 Zeek log files:
  - conn.log
  - dns.log
  - http.log
  - ssl.log

Testing PostgreSQL VM Connection...
✓ PostgreSQL connected: PostgreSQL 15.5 on x86_64-pc-linux-gnu...
✓ Found 6 Zeek tables...

======================================================================
                       Connectivity Summary
======================================================================
FastAPI local setup: ok
Zeek VM (35.222.249.202): connected
PostgreSQL VM (34.132.194.35): connected

✓ All connectivity tests PASSED - System is ready!
```

---

## Quick Start - Pulling Zeek Logs

### Method 1: Via FastAPI HTTP Endpoint

```bash
# Make sure FastAPI is running
# Then ingest a log file:

curl -X GET "http://34.170.121.14:8000/zeek/remote/ingest-log?filename=conn.log" \
  -H "Content-Type: application/json" | jq .

# Bulk ingest all logs:
curl -X POST "http://34.170.121.14:8000/zeek/remote/ingest-all" \
  -H "Content-Type: application/json" | jq .
```

### Method 2: Via Python Script

```python
import asyncio
from backend.app.zeek_remote_client import ZeekRemoteClient, PostgresIngester

async def main():
    # Initialize client
    zeek_client = ZeekRemoteClient()
    postgres_ingester = PostgresIngester()
    
    # Connect
    if not await zeek_client.connect():
        print("Failed to connect to Zeek VM")
        return
    
    # Initialize PostgreSQL
    if not await postgres_ingester.init_pool():
        print("Failed to connect to PostgreSQL")
        return
    
    # Ensure tables
    await postgres_ingester.ensure_tables()
    
    # Get and ingest logs
    files = await zeek_client.list_log_files()
    
    for filename in files:
        content = await zeek_client.get_log_content(filename)
        if content:
            processed, inserted = await postgres_ingester.parse_and_ingest_log_content(
                content,
                filename
            )
            print(f"{filename}: {inserted} events inserted")
    
    # Cleanup
    await zeek_client.disconnect()
    await postgres_ingester.close_pool()

asyncio.run(main())
```

---

## Troubleshooting

### Connection Issues

**Problem**: `Cannot connect to Zeek VM`

**Solution**:
1. Verify network connectivity: `ping 35.222.249.202`
2. Verify SSH port is open: `nc -zv 35.222.249.202 22`
3. Check SSH credentials
4. Run: `python3 test_connectivity.py`

---

**Problem**: `PostgreSQL connection refused`

**Solution**:
1. Verify PostgreSQL is running on 34.132.194.35
2. Check firewall rules allow port 5432
3. Verify credentials in POSTGRES_URL
4. Test with: `psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db`

---

**Problem**: `No Zeek logs found`

**Solution**:
1. SSH into Zeek VM and check path: `ssh zauguste52@35.222.249.202`
2. List files: `ls -la /opt/zeek/logs/current/`
3. Check if Zeek is generating logs: `zeekctl status`
4. Update `ZEEK_REMOTE_PATH` if different

---

## Performance Considerations

- **Log file size**: Each log file is loaded entirely into memory
  - For large files (>1GB), consider splitting
- **Batch processing**: Bulk ingest runs all files sequentially
  - Consider parallelizing for 20+ log files
- **Database indexes**: Queries on timestamp, IP addresses are optimized
- **Connection pool**: 5 concurrent PostgreSQL connections by default

---

## Security Best Practices

1. **SSH Keys**: Use key-based authentication instead of passwords
   - Generate: `ssh-keygen -t rsa -b 4096`
   - Copy: `ssh-copy-id -i ~/.ssh/id_rsa.pub zauguste52@35.222.249.202`

2. **PostgreSQL**: Restrict network access
   - Only allow FastAPI VM (34.170.121.14)
   - Edit `/etc/postgresql/*/main/pg_hba.conf`:
     ```
     host    cybercyte_db    postgres    34.170.121.14/32    md5
     ```

3. **Environment Variables**: Never commit `.env` to version control
   - Add `.env` to `.gitignore`
   - Use secrets management in production

---

## Next Steps

1. **Run connectivity test**: `python3 test_connectivity.py`
2. **Start FastAPI**: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
3. **Ingest logs**: `curl http://34.170.121.14:8000/zeek/remote/ingest-log?filename=conn.log`
4. **Query results**: `psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db`

---

## Architecture Notes

- **Zeek VM**: Generates security logs - no FastAPI needed there
- **FastAPI VM**: Acts as orchestrator/bridge between Zeek and PostgreSQL
- **PostgreSQL VM**: Centralized data store for all events
- **Data flow**: Unidirectional (Zeek → FastAPI → PostgreSQL)
- **No data stored on FastAPI VM**: Logs are streamed through

---

*Documentation updated: December 5, 2025*
