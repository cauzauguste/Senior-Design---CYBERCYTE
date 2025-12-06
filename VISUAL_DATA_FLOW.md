# Visual Data Flow Diagram - Cybercyte Zeek Integration

## Complete System Architecture

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           CYBERCYTE THREE-VM ARCHITECTURE - COMPLETE DATA FLOW               ║
║                                                                              ║
║                          December 5, 2025                                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝


┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  VM 1: ZEEK SENSOR (35.222.249.202)                                        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Network Interface                                                  │   │
│  │  ├─ Monitors all traffic                                           │   │
│  │  └─ Records security events                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Zeek IDS Engine                                                    │   │
│  │  ├─ Connection tracking (conn.log)                                 │   │
│  │  ├─ DNS queries (dns.log)                                          │   │
│  │  ├─ HTTP traffic (http.log)                                        │   │
│  │  ├─ SSL/TLS events (ssl.log)                                       │   │
│  │  ├─ File analysis (files.log)                                      │   │
│  │  └─ Other events                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Zeek Logs Directory                                                │   │
│  │  /opt/zeek/logs/current/                                            │   │
│  │                                                                     │   │
│  │  [conn.log]          [dns.log]          [http.log]                │   │
│  │  ├─ uid               ├─ query           ├─ uri                   │   │
│  │  ├─ id.orig_h         ├─ rcode           ├─ method               │   │
│  │  ├─ id.resp_h         ├─ answers         ├─ status_code          │   │
│  │  ├─ proto             └─ response_time   └─ user_agent           │   │
│  │  └─ duration                                                      │   │
│  │                                                                     │   │
│  │  [ssl.log]           [files.log]                                  │   │
│  │  ├─ server_name       ├─ file_id                                  │   │
│  │  ├─ cipher            ├─ md5_hash                                 │   │
│  │  └─ version           └─ sha256_hash                              │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│                  SSH/SFTP Server (Port 22) - ACTIVE                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │  
                                  │  SFTP Download (Encrypted)
                                  │  1. Connect to port 22
                                  │  2. Authenticate (SSH key or password)
                                  │  3. List files in /opt/zeek/logs/current/
                                  │  4. Download .log files
                                  │
                                  ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  VM 2: FASTAPI BACKEND (34.170.121.14)                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Application (Port 8000)                                    │   │
│  │                                                                     │   │
│  │  ┌─ /zeek/remote/health              (Test connectivity)         │   │
│  │  ├─ /zeek/remote/list-logs           (List available logs)       │   │
│  │  ├─ /zeek/remote/ingest-log          (Download 1 log file)       │   │
│  │  ├─ /zeek/remote/ingest-all          (Download all logs)         │   │
│  │  └─ /zeek/remote/test-connection     (Full diagnostics)          │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  backend/app/zeek_remote_client.py                                  │   │
│  │                                                                     │   │
│  │  ┌──────────────────────────────────────────────────────────────┐  │   │
│  │  │  ZeekRemoteClient Class                                      │  │   │
│  │  │  ├─ connect()          → SSH/SFTP to Zeek VM               │  │   │
│  │  │  ├─ list_log_files()   → Get available files               │  │   │
│  │  │  ├─ get_log_content()  → Download specific file            │  │   │
│  │  │  └─ disconnect()       → Close connections                 │  │   │
│  │  └──────────────────────────────────────────────────────────────┘  │   │
│  │                                                                     │   │
│  │  ┌──────────────────────────────────────────────────────────────┐  │   │
│  │  │  PostgresIngester Class                                      │  │   │
│  │  │  ├─ init_pool()                  → Create DB connections   │  │   │
│  │  │  ├─ ensure_tables()              → Create schema           │  │   │
│  │  ├─ parse_zeek_json_line()         → Parse JSON             │  │   │
│  │  ├─ parse_and_ingest_log_content() → Batch insert           │  │   │
│  │  ├─ insert_connection()             → Insert conn.log events  │  │   │
│  │  ├─ insert_dns_event()              → Insert dns.log events   │  │   │
│  │  └─ insert_zeek_event()             → Insert generic events   │  │   │
│  │  └──────────────────────────────────────────────────────────────┘  │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│          PARSING PROCESS:        │                                           │
│          ─────────────────        ▼                                           │
│          1. Download file                                                    │
│          2. Split by newlines     ┌──────────────────────────────────┐      │
│          3. Skip comments (#)     │  Log Content (JSON Format)       │      │
│          4. Parse JSON            │                                  │      │
│          5. Route by type         │  {"ts":1701753600,               │      │
│          6. Batch 100 rows        │   "uid":"CAqnQK4abc",            │      │
│          7. INSERT to DB          │   "id.orig_h":"192.168.1.100",   │      │
│                                    │   "id.resp_h":"8.8.8.8",         │      │
│                                    │   "proto":"udp", ...}            │      │
│                                    │                                  │      │
│                                    │  {"ts":1701753601,               │      │
│                                    │   "uid":"CAqnQK4def", ...}      │      │
│                                    │                                  │      │
│                                    └──────────────────────────────────┘      │
│                                 │                                           │
│                      asyncpg connection pool                               │
│                    (5 concurrent connections)                             │
│                                 │                                           │
│                PostgreSQL Protocol (TCP/5432)                             │
│                                 │                                           │
└─────────────────────────────────│───────────────────────────────────────────┘
                                  │
                                  │  
                                  │  BULK INSERT
                                  │  INSERT INTO zeek_connections VALUES (...)
                                  │  INSERT INTO zeek_dns VALUES (...)
                                  │  INSERT INTO zeek_events VALUES (...)
                                  │
                                  ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  VM 3: POSTGRESQL DATABASE (34.132.194.35)                                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PostgreSQL 15 Database (Port 5432)                                 │   │
│  │  Database: cybercyte_db                                             │   │
│  │                                                                     │   │
│  │  ┌────────────────────────────────┬────────────────────────────┐   │   │
│  │  │ zeek_connections               │ zeek_dns                  │   │   │
│  │  ├─ uid                           ├─ uid                      │   │   │
│  │  ├─ source_ip (indexed)           ├─ query (indexed)          │   │   │
│  │  ├─ dest_ip (indexed)             ├─ source_ip (indexed)      │   │   │
│  │  ├─ source_port                   ├─ query_type               │   │   │
│  │  ├─ dest_port                     ├─ rcode                    │   │   │
│  │  ├─ protocol                      ├─ answers                  │   │   │
│  │  ├─ duration                      └─ raw_data (JSONB)         │   │   │
│  │  ├─ bytes_sent                                                │   │   │
│  │  ├─ bytes_received                ┌────────────────────────┐  │   │   │
│  │  ├─ connection_state              │ zeek_events (generic)  │  │   │   │
│  │  ├─ raw_data (JSONB)              ├─ log_type (indexed)    │  │   │   │
│  │  ├─ timestamp (indexed)           ├─ source_ip (indexed)   │  │   │   │
│  │  └─ created_at                    ├─ dest_ip (indexed)     │  │   │   │
│  │                                   ├─ timestamp (indexed)   │  │   │   │
│  │  ┌────────────────────────────────┤─ severity              │  │   │   │
│  │  │ zeek_http                      ├─ raw_data (JSONB)      │  │   │   │
│  │  ├─ uid                           └─ event_text            │  │   │   │
│  │  ├─ uri                                                    │  │   │   │
│  │  ├─ method                        ┌────────────────────┐   │   │   │   │
│  │  ├─ status_code                   │ zeek_ssl           │   │   │   │   │
│  │  ├─ host                          ├─ uid               │   │   │   │   │
│  │  ├─ user_agent                    ├─ server_name       │   │   │   │   │
│  │  └─ raw_data (JSONB)              ├─ cipher            │   │   │   │   │
│  │                                   ├─ version           │   │   │   │   │
│  │  ┌────────────────────────────────┤─ raw_data (JSONB)  │   │   │   │   │
│  │  │ zeek_files                     └────────────────────┘   │   │   │   │
│  │  ├─ file_name                                              │   │   │   │
│  │  ├─ md5_hash                                               │   │   │   │
│  │  ├─ sha1_hash                                              │   │   │   │
│  │  ├─ sha256_hash                                            │   │   │   │
│  │  └─ raw_data (JSONB)                                       │   │   │   │
│  │                                                             │   │   │   │
│  └─────────────────────────────────────────────────────────────┘   │   │
│                                                                     │   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Indexes (for fast queries):                                    │   │
│  │  ├─ idx_zeek_*_timestamp          → Time-based searches        │   │
│  │  ├─ idx_zeek_*_source_ip          → Source IP lookups          │   │
│  │  ├─ idx_zeek_*_dest_ip            → Destination IP lookups     │   │
│  │  ├─ idx_zeek_events_log_type      → Event type filtering       │   │
│  │  └─ idx_zeek_dns_query            → DNS query searches         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                     │   │
└─────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════

                            QUERY EXAMPLES

═══════════════════════════════════════════════════════════════════════════════

From FastAPI VM (34.170.121.14):

1. List available logs on Zeek VM:
   GET /zeek/remote/list-logs
   └─→ Returns: ["conn.log", "dns.log", "http.log", "ssl.log"]

2. Download and ingest connection logs:
   GET /zeek/remote/ingest-log?filename=conn.log
   └─→ Returns: {lines_processed: 1250, lines_inserted: 1248}

3. Query results from PostgreSQL:
   psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db
   └─→ SELECT * FROM zeek_connections WHERE source_ip = '192.168.1.100';
   └─→ SELECT COUNT(*) FROM zeek_dns WHERE query LIKE '%.com';
   └─→ SELECT * FROM zeek_http WHERE status_code >= 400 ORDER BY timestamp DESC;


═══════════════════════════════════════════════════════════════════════════════

                            AUTHENTICATION FLOW

═══════════════════════════════════════════════════════════════════════════════

SSH/SFTP to Zeek VM (35.222.249.202):
┌──────────────────────────────────────────┐
│  1. FastAPI reads ZEEK_SSH_KEY from .env  │
│  2. Loads private key file                │
│  3. Initiates SSH connection on port 22   │
│  4. Authenticates as zauguste52           │
│  5. Opens SFTP channel                    │
│  6. Navigates to /opt/zeek/logs/current/  │
│  7. Lists and downloads .log files        │
│  8. Closes SFTP channel                   │
└──────────────────────────────────────────┘

PostgreSQL Authentication (34.132.194.35:5432):
┌──────────────────────────────────────────┐
│  1. FastAPI reads POSTGRES_URL from .env  │
│  2. Parses: user, password, host, port    │
│  3. Creates asyncpg connection pool       │
│  4. Establishes TCP connections (5 max)   │
│  5. Sends authentication credentials      │
│  6. PostgreSQL verifies with pg_hba.conf  │
│  7. Connection ready for queries          │
│  8. Maintains pool for reuse              │
└──────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════

                            DATA TRANSFORMATION

═══════════════════════════════════════════════════════════════════════════════

Input (Zeek JSON):
┌──────────────────────────────────────────────────────────────────────┐
│  {"ts":1701753600.1,"uid":"CAqnQK4abc","id.orig_h":"192.168.1.100", │
│   "id.orig_p":54321,"id.resp_h":"8.8.8.8","id.resp_p":53,"proto":   │
│   "udp","service":"dns","duration":0.5,"orig_bytes":128,...}         │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ PostgresIngester.parse_zeek_json_line()
                                  
Parsed Python Dict:
┌──────────────────────────────────────────────────────────────────────┐
│  {                                                                   │
│    "ts": 1701753600.1,                                               │
│    "uid": "CAqnQK4abc",                                              │
│    "id.orig_h": "192.168.1.100",                                     │
│    "id.resp_h": "8.8.8.8",                                           │
│    ...                                                               │
│  }                                                                   │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ Route by log type (conn.log)
                                  
PostgreSQL INSERT:
┌──────────────────────────────────────────────────────────────────────┐
│  INSERT INTO zeek_connections                                        │
│    (uid, source_ip, dest_ip, source_port, dest_port, protocol,      │
│     duration, bytes_sent, bytes_received, connection_state,         │
│     raw_data, timestamp)                                             │
│  VALUES                                                              │
│    ('CAqnQK4abc', '192.168.1.100'::inet, '8.8.8.8'::inet, 54321,   │
│     53, 'udp', 0.5, 128, 256, 'SF', '{"ts":1701753600.1,...}'::    │
│     jsonb, '2023-12-05 12:00:00');                                   │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ PostgreSQL stores row
                                  
Stored in Database:
┌──────────────────────────────────────────────────────────────────────┐
│ id │ uid      │ source_ip    │ dest_ip │ source_port │ dest_port │ ..
│────┼──────────┼──────────────┼─────────┼─────────────┼───────────┼──
│ 1  │ CAqnQK4a │ 192.168.1... │ 8.8.... │ 54321       │ 53       │ ..
└──────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════

                            ERROR HANDLING

═══════════════════════════════════════════════════════════════════════════════

⚠ SSH Connection Fails:
  → Log error message
  → Return HTTP 500 with error details
  → Suggest troubleshooting steps

⚠ Log File Not Found:
  → Return HTTP 404 with filename
  → Suggest checking list-logs endpoint

⚠ PostgreSQL Insert Fails:
  → Log error message
  → Continue with next record
  → Return count of successfully inserted rows

⚠ Parsing Error (invalid JSON):
  → Skip the malformed line
  → Continue processing
  → Log for debugging


═══════════════════════════════════════════════════════════════════════════════

                            DEPLOYMENT STATUS

═══════════════════════════════════════════════════════════════════════════════

VM 1 (Zeek Sensor - 35.222.249.202):
  ✓ SSH/SFTP Server (port 22)
  ✓ Zeek IDS running and generating logs
  ✓ Logs in /opt/zeek/logs/current/
  → No changes needed

VM 2 (FastAPI - 34.170.121.14):
  ✓ FastAPI running (port 8000)
  ✓ zeek_remote_client.py installed
  ✓ routes/zeek_remote.py registered
  ✓ 5 new endpoints active
  → Ready for use

VM 3 (PostgreSQL - 34.132.194.35):
  ✓ PostgreSQL running (port 5432)
  ✓ cybercyte_db database created
  ✓ zeek_* tables created
  ✓ Indexes optimized
  → Ready to receive data


═══════════════════════════════════════════════════════════════════════════════

Generated: December 5, 2025
```

---

## Summary Table

| Component | IP Address | Port | Protocol | Purpose |
|-----------|-----------|------|----------|---------|
| Zeek Sensor | 35.222.249.202 | 22 | SSH/SFTP | Log generation & retrieval |
| FastAPI | 34.170.121.14 | 8000 | HTTP | Orchestration & API |
| PostgreSQL | 34.132.194.35 | 5432 | TCP | Event storage |

---

*This diagram represents the complete data flow for the Cybercyte remote Zeek integration system.*
