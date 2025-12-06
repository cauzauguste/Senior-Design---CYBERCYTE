# Zeek Log Integration Guide

This document explains how to integrate Zeek IDS logs with PostgreSQL on a separate VM for security event analysis and storage.

## Quick Start

### Architecture

Your system will have:
- **Zeek Sensor VM**: Runs Zeek IDS, generates logs, runs log reader service
- **Database/API VM**: Runs PostgreSQL, FastAPI backend, Streamlit dashboard

### Fastest Deployment (Docker Compose)

1. **On Database VM:**

```bash
cd /home/zauguste52/Senior-Design---CYBERCYTE
docker-compose up -d postgres api dashboard
```

2. **On Zeek Sensor VM:**

```bash
# Install requirements
pip install -r requirements.txt

# Create .env file
cat > .env << 'EOF'
POSTGRES_URL=postgresql://postgres:pass@<DATABASE_VM_IP>:5432/cybercyte_db
ZEEK_LOG_DIR=/opt/zeek/logs/current
ZEEK_PROCESSED_DIR=/opt/zeek/logs/processed
ZEEK_POLL_INTERVAL=10
EOF

# Run the service
python -m backend.app.zeek_log_reader
```

## What's New

### New Files Created:

1. **`backend/app/zeek_log_reader.py`** - Main service that:
   - Monitors Zeek log directory for new files
   - Parses Zeek JSON logs
   - Stores events in PostgreSQL tables
   - Supports multiple Zeek log types (conn, dns, http, ssl, files)

2. **`backend/app/routes/zeek.py`** - API endpoints:
   - `GET /zeek/events/zeek/all` - All Zeek events
   - `GET /zeek/events/zeek/connections` - Connection logs
   - `GET /zeek/events/zeek/dns` - DNS queries
   - `GET /zeek/events/zeek/files` - File hashes and integrity
   - `GET /zeek/events/zeek/http` - HTTP requests
   - `GET /zeek/events/zeek/ssl` - SSL/TLS events
   - `GET /zeek/events/zeek/stats` - Event statistics
   - `GET /zeek/events/zeek/suspicious-ips` - Suspicious IPs

3. **`docker-compose.yml`** - Multi-service deployment:
   - PostgreSQL database
   - FastAPI backend
   - Zeek log reader
   - Streamlit dashboard

4. **`ZEEK_SETUP_GUIDE.md`** - Detailed setup instructions

### Updated Files:

1. **`backend/app/database.py`**
   - Now supports `POSTGRES_URL` environment variable
   - Works with remote PostgreSQL instances
   - Added connection pooling

2. **`backend/app/models.py`**
   - Added 6 new Zeek-specific models:
     - `ZeekEvent` - Generic security events
     - `ZeekConnection` - Connection tracking
     - `ZeekDNS` - DNS events
     - `ZeekFile` - File hashing
     - `ZeekHTTP` - HTTP traffic
     - `ZeekSSL` - SSL/TLS events

3. **`backend/app/schemas.py`**
   - Added Pydantic schemas for all Zeek models

4. **`backend/app/main.py`**
   - Included Zeek routes in FastAPI app

5. **`requirements.txt`**
   - Added `asyncpg` for async PostgreSQL
   - Added `aiokafka` and `kafka-python`

6. **`conf.env`**
   - Comprehensive environment configuration
   - Comments for deployment on separate VMs

## Database Schema

### Main Zeek Tables

```sql
-- All security events (generic)
zeek_events (id, timestamp, log_type, source_ip, dest_ip, ...)

-- Network connections
zeek_connections (id, uid, source_ip, dest_ip, bytes_sent, bytes_received, ...)

-- DNS queries
zeek_dns (id, uid, query, qtype, rcode, answers, ...)

-- File integrity
zeek_files (id, file_name, md5_hash, sha256_hash, ...)

-- HTTP traffic
zeek_http (id, uid, method, uri, status_code, ...)

-- SSL/TLS connections
zeek_ssl (id, uid, version, cipher, server_name, established, ...)
```

All tables include:
- Proper indexing on frequently queried columns
- JSON storage for raw Zeek data
- Timestamps for temporal analysis
- Organized by log type for efficient queries

## Configuration

### Environment Variables

```bash
# PostgreSQL Connection (required)
POSTGRES_URL=postgresql://username:password@host:5432/database

# Zeek Log Reader (required on Zeek VM)
ZEEK_LOG_DIR=/opt/zeek/logs/current
ZEEK_PROCESSED_DIR=/opt/zeek/logs/processed
ZEEK_POLL_INTERVAL=10  # seconds

# Optional SSL/TLS
POSTGRES_CA_FILE=/path/to/ca-cert.pem
```

### File Locations

- **Zeek Logs**: `/opt/zeek/logs/current/`
- **Processed Logs**: `/opt/zeek/logs/processed/`
- **Config File**: `.env` in repo root

## Supported Log Types

### Automatically Parsed:

| Log Type | Table | Description |
|----------|-------|-------------|
| conn | zeek_connections | Network connections |
| dns | zeek_dns | DNS queries/responses |
| http | zeek_http | HTTP requests |
| ssl | zeek_ssl | SSL/TLS events |
| files | zeek_files | File integrity |
| * | zeek_events | Other events |

### Log Format Support:

- ✅ JSON format (primary)
- ✅ Tab-separated format (basic support)
- ✅ Zeek standard output

## Usage Examples

### Query Recent Security Events

```bash
curl http://localhost:8080/zeek/events/zeek/all?limit=10
```

### Find Suspicious IPs

```bash
curl http://localhost:8080/zeek/events/zeek/suspicious-ips?hours=24&min_events=10
```

### Check DNS Activity

```bash
curl "http://localhost:8080/zeek/events/zeek/dns?query_string=example.com"
```

### Get File Hashes

```bash
curl "http://localhost:8080/zeek/events/zeek/files?hash_type=sha256&hash_value=abc123..."
```

### View Statistics

```bash
curl http://localhost:8080/zeek/events/zeek/stats?hours=24
```

## Deployment Steps

### 1. Prepare Database VM

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Start services
docker-compose up -d
```

### 2. Prepare Zeek Sensor VM

```bash
# Install Python 3.10+
sudo apt-get install python3.10 python3-pip

# Create virtual environment
python3.10 -m venv zeek-env
source zeek-env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
nano .env
# Add: POSTGRES_URL=postgresql://postgres:pass@<DB_IP>:5432/cybercyte_db
# Add: ZEEK_LOG_DIR=/opt/zeek/logs/current
```

### 3. Run Zeek Log Reader

```bash
# Manual run (for testing)
python -m backend.app.zeek_log_reader

# As systemd service (for production)
sudo systemctl start zeek-log-reader
```

### 4. Verify Data Flow

```bash
# Check PostgreSQL
psql -U postgres -d cybercyte_db -c "SELECT COUNT(*) FROM zeek_events;"

# Check API
curl http://localhost:8080/health
curl http://localhost:8080/zeek/events/zeek/stats

# View dashboard
open http://localhost:8501
```

## Troubleshooting

### PostgreSQL Connection Fails

```bash
# Test connectivity
psql postgresql://postgres:pass@<IP>:5432/cybercyte_db

# Check PostgreSQL is listening
netstat -tulnp | grep 5432

# Verify firewall
sudo ufw allow 5432
```

### Zeek Logs Not Being Read

```bash
# Check log directory exists
ls -la /opt/zeek/logs/current/

# Check permissions
sudo chmod 755 /opt/zeek/logs/current

# Check zeek_log_reader is running
ps aux | grep zeek_log_reader

# View error logs
tail -f zeek-log-reader.log
```

### High Memory Usage

- Reduce `ZEEK_POLL_INTERVAL`
- Implement log rotation on Zeek
- Archive processed logs regularly
- Monitor with: `SELECT COUNT(*) FROM zeek_events;`

## Advanced Configuration

### Custom Log Parsing

Edit `zeek_log_reader.py` to add custom parsers:

```python
async def insert_custom_event(custom_data: Dict):
    # Custom parsing logic
    if custom_data.get("log_type") == "custom":
        await insert_zeek_event(...)
```

### Batch Processing

For high-volume environments:

```python
# Modify zeek_log_reader.py
BATCH_SIZE = 1000

async def batch_insert_events(events):
    async with db_pool.acquire() as conn:
        await conn.executemany(INSERT_QUERY, events)
```

### Data Retention Policy

```sql
-- Archive old data monthly
DELETE FROM zeek_events 
WHERE created_at < CURRENT_DATE - INTERVAL '90 days';
```

## Performance Tips

1. **Indexing**: Already optimized on key columns
2. **Partitioning**: Consider for > 100M rows
3. **Archiving**: Move old logs to separate storage
4. **Connection Pooling**: Already configured
5. **Batch Inserts**: Enable for high-volume (see Advanced)

## Security Considerations

- [ ] Change default PostgreSQL password
- [ ] Enable SSL/TLS for database connections
- [ ] Restrict network access to database port
- [ ] Use secrets manager for credentials
- [ ] Enable PostgreSQL audit logging
- [ ] Set up database backups
- [ ] Monitor service logs for errors
- [ ] Use non-root user for service

## Support & Resources

- **Zeek Documentation**: https://docs.zeek.org/
- **FastAPI Docs**: http://localhost:8080/docs
- **PostgreSQL Docs**: https://www.postgresql.org/docs/
- **Issue Tracking**: Check project GitHub

## Next Steps

1. **Query Optimization**: Add more API filters
2. **Threat Detection**: Implement alerting rules
3. **Dashboard**: Create Streamlit visualizations
4. **Integration**: Connect to SIEM or ticketing system
5. **Machine Learning**: Build anomaly detection
