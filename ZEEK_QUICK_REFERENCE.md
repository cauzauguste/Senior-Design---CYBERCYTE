# Cybercyte Remote Zeek Integration - Quick Reference Card

## Architecture at a Glance

```
Zeek VM (35.222.249.202)  →  FastAPI VM (34.170.121.14)  →  PostgreSQL VM (34.132.194.35)
Generates logs            →  Retrieves & Parses logs    →  Stores events
SSH/SFTP (port 22)        →  Connections (asyncpg)      →  TCP/5432
```

---

## Getting Started (5 Minutes)

### 1. Set Environment Variables
```bash
# Edit/create .env in project root
ZEEK_REMOTE_HOST=35.222.249.202
ZEEK_REMOTE_USER=zauguste52
ZEEK_SSH_KEY=/home/zauguste52/.ssh/id_rsa  # or use password
POSTGRES_URL=postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db
```

### 2. Test Connectivity
```bash
python3 test_connectivity.py
```

Expected output:
- ✓ FastAPI local setup: ok
- ✓ Zeek VM: connected
- ✓ PostgreSQL VM: connected

### 3. Start FastAPI
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### 4. Ingest Logs
```bash
curl "http://34.170.121.14:8000/zeek/remote/ingest-log?filename=conn.log" | jq .
```

### 5. Verify in PostgreSQL
```bash
psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db -c \
  "SELECT COUNT(*) FROM zeek_connections;"
```

---

## API Endpoints

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/zeek/remote/health` | GET | Test VM connectivity | `{zeek_vm, postgres_vm, overall}` |
| `/zeek/remote/list-logs` | GET | List logs on Zeek VM | `{log_files, count}` |
| `/zeek/remote/ingest-log?filename=X` | GET | Download & ingest 1 file | `{lines_processed, lines_inserted}` |
| `/zeek/remote/ingest-all` | POST | Ingest all files | `{status: ingestion_started}` |
| `/zeek/remote/test-connection` | GET | Detailed diagnostics | `{zeek_vm, postgres_vm, connectivity}` |

---

## Common Commands

### Check System Status
```bash
# Quick health check
curl http://34.170.121.14:8000/zeek/remote/health | jq .

# Detailed diagnostics
curl http://34.170.121.14:8000/zeek/remote/test-connection | jq .
```

### List Available Logs
```bash
curl http://34.170.121.14:8000/zeek/remote/list-logs | jq '.log_files'
```

### Ingest Specific Log Types
```bash
# Connection logs
curl "http://34.170.121.14:8000/zeek/remote/ingest-log?filename=conn.log"

# DNS queries
curl "http://34.170.121.14:8000/zeek/remote/ingest-log?filename=dns.log"

# HTTP traffic
curl "http://34.170.121.14:8000/zeek/remote/ingest-log?filename=http.log"

# SSL/TLS connections
curl "http://34.170.121.14:8000/zeek/remote/ingest-log?filename=ssl.log"
```

### Ingest All Logs at Once
```bash
curl -X POST http://34.170.121.14:8000/zeek/remote/ingest-all
```

---

## Database Queries

### View Available Tables
```bash
psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db -c "\dt zeek_*"
```

### Row Counts
```bash
psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db -c \
  "SELECT table_name, 
          (SELECT COUNT(*) FROM public.zeek_events) as zeek_events,
          (SELECT COUNT(*) FROM public.zeek_connections) as zeek_connections,
          (SELECT COUNT(*) FROM public.zeek_dns) as zeek_dns;"
```

### Recent Connections
```bash
psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db -c \
  "SELECT timestamp, source_ip, dest_ip, source_port, dest_port, protocol 
   FROM zeek_connections 
   ORDER BY timestamp DESC 
   LIMIT 10;"
```

### DNS Queries
```bash
psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db -c \
  "SELECT timestamp, source_ip, query, rcode, query_type 
   FROM zeek_dns 
   ORDER BY timestamp DESC 
   LIMIT 10;"
```

### Suspicious IPs
```bash
psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db -c \
  "SELECT dest_ip, COUNT(*) as connection_count 
   FROM zeek_connections 
   GROUP BY dest_ip 
   ORDER BY connection_count DESC 
   LIMIT 20;"
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `backend/app/zeek_remote_client.py` | SFTP client + PostgreSQL ingester |
| `backend/app/routes/zeek_remote.py` | 5 new FastAPI endpoints |
| `backend/app/main.py` | *(Modified)* - Registers new routes |
| `test_connectivity.py` | Comprehensive diagnostics script |
| `ZEEK_REMOTE_INTEGRATION.md` | Detailed architecture documentation |
| `FASTAPI_REMOTE_SETUP.md` | Setup & deployment guide |
| `MULTI_VM_ARCHITECTURE.md` | Visual data flow diagrams |

---

## Troubleshooting

### Connection Issues

| Problem | Solution |
|---------|----------|
| SSH auth fails | Check `ZEEK_SSH_KEY` exists or set `ZEEK_SSH_PASSWORD` |
| Can't reach Zeek VM | `ping 35.222.249.202` / `nc -zv 35.222.249.202 22` |
| PostgreSQL connection refused | Check firewall: `sudo ufw allow from 34.170.121.14 to any port 5432` |
| No logs found on Zeek VM | SSH to 35.222.249.202 and check `/opt/zeek/logs/current/` |

### Performance

| Issue | Solution |
|-------|----------|
| Slow ingestion | Check network latency between VMs |
| High memory usage | Reduce batch size or ingest one file at a time |
| Database slow | Check PostgreSQL indexes with `\d zeek_connections` |

---

## Environment Variables (Complete List)

```bash
# Zeek VM Configuration
ZEEK_REMOTE_HOST=35.222.249.202
ZEEK_REMOTE_PORT=22
ZEEK_REMOTE_USER=zauguste52
ZEEK_REMOTE_PATH=/opt/zeek/logs/current

# SSH Authentication (choose one)
ZEEK_SSH_KEY=/home/zauguste52/.ssh/id_rsa       # Preferred
# OR
ZEEK_SSH_PASSWORD=your_password_here             # Fallback

# PostgreSQL Configuration
POSTGRES_URL=postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db

# Optional SSL/TLS
# POSTGRES_CA_FILE=/path/to/ca-cert.pem
```

---

## Data Flow (Technical)

```
1. Client calls: GET /zeek/remote/ingest-log?filename=conn.log
                                    ↓
2. zeek_remote_client.py:ZeekRemoteClient
   - Connect to 35.222.249.202 via SSH
   - Open SFTP channel
   - Download conn.log from /opt/zeek/logs/current/
                                    ↓
3. zeek_remote_client.py:PostgresIngester
   - Parse each line as JSON
   - Route based on log type (conn → zeek_connections)
   - Prepare INSERT statement
                                    ↓
4. asyncpg connection pool
   - Batch 100 inserts together
   - Execute INSERT to PostgreSQL on 34.132.194.35
                                    ↓
5. PostgreSQL 15
   - Store in zeek_connections table
   - Update indexes
   - Return row count
                                    ↓
6. Response: {"lines_processed": 1000, "lines_inserted": 998}
```

---

## Key Concepts

**SFTP (SSH File Transfer Protocol)**
- Secure file transfer over SSH
- Port 22 (same as SSH)
- Used for downloading logs from Zeek VM

**asyncpg**
- Async PostgreSQL driver for Python
- Connection pooling for efficiency
- Fast bulk inserts

**Zeek JSON Format**
- One JSON object per line
- Each object contains full event data
- 7+ million events per log file typical

**PostgreSQL Tables**
- `zeek_events` - Generic events
- `zeek_connections` - Network connections
- `zeek_dns` - DNS queries
- `zeek_http` - HTTP requests
- `zeek_ssl` - SSL/TLS connections
- `zeek_files` - File hashes/metadata

---

## Production Tips

1. **Use SSH Keys**: More secure than passwords
2. **Set up firewall rules**: Only allow FastAPI VM to connect to PostgreSQL
3. **Monitor log directory**: Set up automated ingestion schedules
4. **Archive old logs**: Move processed logs to separate directory
5. **Set up backups**: PostgreSQL WAL archiving on 34.132.194.35
6. **Enable SSL/TLS**: Use CA certificates for PostgreSQL connection
7. **Set resource limits**: Limit connection pool size based on capacity

---

## Quick Links

- **FastAPI Docs**: `http://34.170.121.14:8000/docs`
- **FastAPI Redoc**: `http://34.170.121.14:8000/redoc`
- **Health Check**: `http://34.170.121.14:8000/health`
- **New Endpoints**: `http://34.170.121.14:8000/docs#/Zeek%20Remote%20Integration`

---

*Last Updated: December 5, 2025*
