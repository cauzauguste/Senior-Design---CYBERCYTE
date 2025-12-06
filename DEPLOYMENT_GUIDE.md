# CYBERCYTE Zeek Integration - Complete Deployment Guide

## Overview

Your system is now configured to allow PostgreSQL on a separate VM to read Zeek security logs and store them in a centralized database. This document provides step-by-step deployment instructions.

## What Was Implemented

### 1. Zeek Log Reader Service (`zeek_log_reader.py`)
- Monitors Zeek log directory for new files
- Parses Zeek JSON logs in real-time
- Automatically inserts events into PostgreSQL
- Supports automatic log rotation and archiving

### 2. Database Schema
6 specialized tables for different Zeek log types:
- `zeek_events` - Generic security events
- `zeek_connections` - Network connections (conn.log)
- `zeek_dns` - DNS queries (dns.log)
- `zeek_files` - File integrity/hashing (files.log)
- `zeek_http` - HTTP traffic (http.log)
- `zeek_ssl` - SSL/TLS events (ssl.log)

### 3. API Endpoints
RESTful API for querying Zeek data:
- `/zeek/events/zeek/all` - All events with pagination
- `/zeek/events/zeek/connections` - Filter connections by IP
- `/zeek/events/zeek/dns` - Search DNS queries
- `/zeek/events/zeek/files` - Find files by hash
- `/zeek/events/zeek/http` - Query HTTP traffic
- `/zeek/events/zeek/ssl` - Check SSL/TLS connections
- `/zeek/events/zeek/stats` - Get statistics
- `/zeek/events/zeek/suspicious-ips` - Find suspicious IPs

### 4. Docker Deployment
- `docker-compose.yml` - Full stack deployment
- `Dockerfile.zeek-reader` - Containerized Zeek service
- `Dockerfile.streamlit` - Containerized dashboard

### 5. Documentation
- `ZEEK_README.md` - Quick reference guide
- `ZEEK_SETUP_GUIDE.md` - Detailed setup instructions

## Deployment Scenario

```
┌──────────────────────────────┐
│  Zeek Sensor VM (Linux)      │
│                              │
│  Zeek IDS                    │
│  └─ Generates logs           │
│                              │
│  zeek_log_reader.py          │
│  └─ Reads & parses logs      │
│     Sends to PostgreSQL      │
└───────────┬──────────────────┘
            │ TCP/Port 5432
            │ PostgreSQL Protocol
            ▼
┌──────────────────────────────┐
│  Database/API VM (Linux)     │
│                              │
│  PostgreSQL 15               │
│  ├─ Stores Zeek events       │
│  ├─ Indexes for fast queries │
│  └─ Automatic backups        │
│                              │
│  FastAPI Backend (8080)      │
│  ├─ Zeek API endpoints       │
│  ├─ Dashboard routes         │
│  └─ Authentication           │
│                              │
│  Streamlit Dashboard (8501)  │
│  └─ Visualizations           │
└──────────────────────────────┘
```

## Step 1: Database VM Setup

### Option A: Docker Compose (Recommended for most users)

```bash
# Navigate to project directory
cd /home/zauguste52/Senior-Design---CYBERCYTE

# Start all services
docker-compose up -d

# Verify services are running
docker ps

# Check logs
docker logs cybercyte-postgres
docker logs cybercyte-api

# Access services
# API: http://localhost:8080/docs
# Dashboard: http://localhost:8501
# API Health: http://localhost:8080/health
```

### Option B: Manual Installation

```bash
# Install PostgreSQL 15
sudo apt-get update
sudo apt-get install -y postgresql-15 postgresql-contrib-15

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database
sudo -u postgres createdb cybercyte_db

# Create tables (will be done by app on first run)
# Tables are created automatically when zeek_log_reader connects

# Install Python dependencies
pip install -r requirements.txt

# Run API
uvicorn backend.app.main:app --host 0.0.0.0 --port 8080
```

## Step 2: Zeek Sensor VM Setup

### Installation

```bash
# Install Python 3.10+
sudo apt-get update
sudo apt-get install -y python3.10 python3-pip python3.10-venv

# Navigate to project directory (clone if not present)
git clone <repository-url> /opt/cybercyte
cd /opt/cybercyte

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify Zeek is running
zeekctl status
# Or check for logs
ls -la /opt/zeek/logs/current/
```

### Configuration

Create `.env` file on Zeek sensor VM:

```bash
cat > /opt/cybercyte/.env << 'EOF'
# PostgreSQL connection - REPLACE WITH YOUR DATABASE VM IP
POSTGRES_URL=postgresql://postgres:pass@192.168.1.100:5432/cybercyte_db

# Zeek log configuration
ZEEK_LOG_DIR=/opt/zeek/logs/current
ZEEK_PROCESSED_DIR=/opt/zeek/logs/processed
ZEEK_POLL_INTERVAL=10

# Logging
LOG_LEVEL=INFO
EOF
```

**Important**: Replace `192.168.1.100` with your actual Database VM IP address.

### Verify Connection

Test PostgreSQL connectivity:

```bash
cd /opt/cybercyte

python3 << 'EOF'
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

async def test():
    load_dotenv()
    url = os.getenv("POSTGRES_URL")
    print(f"Testing connection to: {url}")
    
    try:
        pool = await asyncpg.create_pool(url, min_size=1, max_size=5)
        async with pool.acquire() as conn:
            version = await conn.fetchval("SELECT version();")
            print(f"✓ Connected! PostgreSQL: {version}")
        await pool.close()
    except Exception as e:
        print(f"✗ Connection failed: {e}")

asyncio.run(test())
EOF
```

## Step 3: Run Zeek Log Reader

### Option A: Direct Execution (Testing)

```bash
cd /opt/cybercyte
source venv/bin/activate
python -m backend.app.zeek_log_reader
```

You should see:
```
2024-03-15 10:30:45,123 - zeek_log_reader - INFO - PostgreSQL connection pool initialized
2024-03-15 10:30:45,234 - zeek_log_reader - INFO - Zeek tables created/verified
2024-03-15 10:30:45,345 - zeek_log_reader - INFO - Starting Zeek log monitor on directory: /opt/zeek/logs/current
```

### Option B: Using Standalone Script (Simpler)

```bash
cd /opt/cybercyte
python zeek_reader_standalone.py
```

### Option C: As SystemD Service (Production)

Create `/etc/systemd/system/zeek-log-reader.service`:

```ini
[Unit]
Description=Zeek Log Reader Service
After=network.target
Wants=zeek.service

[Service]
Type=simple
User=zeek
WorkingDirectory=/opt/cybercyte
EnvironmentFile=/opt/cybercyte/.env
ExecStart=/opt/cybercyte/venv/bin/python -m backend.app.zeek_log_reader
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable zeek-log-reader
sudo systemctl start zeek-log-reader

# Check status
sudo systemctl status zeek-log-reader

# View logs
sudo journalctl -u zeek-log-reader -f
```

### Option D: Using Docker Container

```bash
docker build -f Dockerfile.zeek-reader -t zeek-reader:latest .

docker run -d \
  --name zeek-log-reader \
  -e POSTGRES_URL="postgresql://postgres:pass@<DATABASE_VM_IP>:5432/cybercyte_db" \
  -e ZEEK_LOG_DIR="/opt/zeek/logs/current" \
  -v /opt/zeek/logs:/zeek/logs \
  zeek-reader:latest
```

## Step 4: Verify Data Flow

### Check Service is Running

**On Zeek Sensor VM:**
```bash
# Method 1: Check process
ps aux | grep zeek_log_reader

# Method 2: Check systemd status
sudo systemctl status zeek-log-reader

# Method 3: Check logs
tail -f zeek-log-reader.log
```

### Check Database has Data

**On Database VM:**
```bash
# Connect to PostgreSQL
psql -U postgres -d cybercyte_db

# Inside psql, check table counts
SELECT COUNT(*) FROM zeek_events;
SELECT COUNT(*) FROM zeek_connections;
SELECT COUNT(*) FROM zeek_dns;

# View recent events
SELECT timestamp, log_type, source_ip, dest_ip, event_text 
FROM zeek_events 
ORDER BY timestamp DESC 
LIMIT 10;

# Exit psql
\q
```

### Test API Endpoints

```bash
# From any machine with network access to Database VM

# Health check
curl http://<DATABASE_VM_IP>:8080/health

# Get Zeek statistics
curl http://<DATABASE_VM_IP>:8080/zeek/events/zeek/stats

# Get recent events
curl http://<DATABASE_VM_IP>:8080/zeek/events/zeek/all?limit=5

# Get suspicious IPs
curl http://<DATABASE_VM_IP>:8080/zeek/events/zeek/suspicious-ips?hours=24

# Interactive API docs
# Open in browser: http://<DATABASE_VM_IP>:8080/docs
```

### View Dashboard

```bash
# Open in browser
http://<DATABASE_VM_IP>:8501
```

## Network Configuration

### Firewall Rules

**On Database VM:**
```bash
# Allow PostgreSQL from Zeek VM
sudo ufw allow from <ZEEK_VM_IP> to any port 5432

# Allow API access
sudo ufw allow 8080
sudo ufw allow 8501
```

**On Zeek Sensor VM:**
```bash
# Outbound PostgreSQL access (should be allowed by default)
sudo ufw allow out 5432 to <DATABASE_VM_IP>
```

### Network Testing

```bash
# From Zeek VM, test connection to Database VM
nc -zv <DATABASE_VM_IP> 5432

# Should output:
# Connection to <DATABASE_VM_IP> 5432 port [tcp/postgresql] succeeded!
```

## Troubleshooting

### Issue: "Connection refused" to PostgreSQL

**Diagnosis:**
```bash
# Check PostgreSQL is running on Database VM
sudo systemctl status postgresql
# or
docker ps | grep postgres
```

**Solutions:**
1. Start PostgreSQL: `sudo systemctl start postgresql`
2. Check PostgreSQL is listening: `sudo netstat -tulnp | grep 5432`
3. Verify correct IP in .env file
4. Check firewall: `sudo ufw status`

### Issue: Zeek logs not being read

**Diagnosis:**
```bash
# Check Zeek is running
zeekctl status

# Check logs exist
ls -la /opt/zeek/logs/current/

# Check permissions
ls -la /opt/zeek/logs/current/conn.log
```

**Solutions:**
1. Start Zeek: `sudo zeekctl start`
2. Wait for logs to be generated (5-10 minutes)
3. Fix permissions: `sudo chown -R zeek:zeek /opt/zeek/logs`
4. Check service logs: `journalctl -u zeek-log-reader -f`

### Issue: High memory/CPU usage

**Causes:**
- Too many logs to process at once
- Inefficient database inserts
- Network latency

**Solutions:**
1. Reduce ZEEK_POLL_INTERVAL (e.g., 30 seconds)
2. Implement batch inserts (see zeek_log_reader.py)
3. Archive old logs to /opt/zeek/logs/processed/
4. Monitor: `SELECT COUNT(*) FROM zeek_events;`

### Issue: No data in dashboard

**Diagnosis:**
```bash
# Check API is running
curl http://localhost:8080/health

# Check database has tables
psql -U postgres -d cybercyte_db -c "\dt"

# Check data exists
psql -U postgres -d cybercyte_db -c "SELECT COUNT(*) FROM zeek_events;"
```

**Solutions:**
1. Wait for Zeek to generate logs (they're created over time)
2. Restart zeek_log_reader service
3. Check service logs for errors
4. Manually test database connection

## Performance Optimization

### For Production Environments:

1. **Batch Inserts**: Modify zeek_log_reader.py to insert in batches of 100-1000

2. **Connection Pooling**: Already optimized in database.py
   - `pool_size=10` (increase if needed)
   - `max_overflow=20` (additional connections)

3. **Indexing**: Already applied to frequently queried columns
   - timestamp
   - source_ip, dest_ip
   - log_type

4. **Archive Strategy**: Move old logs after processing
   ```bash
   # Move logs older than 7 days
   find /opt/zeek/logs/processed -mtime +7 -exec rm {} \;
   ```

5. **Database Maintenance**:
   ```bash
   # Run VACUUM (maintenance)
   sudo -u postgres psql -d cybercyte_db -c "VACUUM ANALYZE;"
   ```

## Security Checklist

- [ ] Change PostgreSQL default password
- [ ] Enable PostgreSQL authentication
- [ ] Use SSL/TLS for database connections
- [ ] Restrict network access to database port
- [ ] Enable firewall on both VMs
- [ ] Use VPN/SSH tunneling for remote access
- [ ] Set up database backups
- [ ] Monitor service logs
- [ ] Use non-root user for service
- [ ] Implement log rotation

## Monitoring & Maintenance

### Daily Checks

```bash
# Service health
sudo systemctl status zeek-log-reader

# Recent errors
sudo journalctl -u zeek-log-reader -n 50

# Database stats
psql -U postgres -d cybercyte_db -c "SELECT COUNT(*) FROM zeek_events;"
```

### Weekly Tasks

```bash
# Archive old logs
find /opt/zeek/logs/processed -mtime +7 -delete

# Check disk usage
df -h

# Database vacuum
sudo -u postgres psql -d cybercyte_db -c "VACUUM ANALYZE;"
```

### Monthly Tasks

```bash
# Backup database
pg_dump -U postgres cybercyte_db > backup-$(date +%Y%m%d).sql

# Review and archive old events
# (implement custom retention policy)
```

## Support

For issues or questions:

1. Check logs: `journalctl -u zeek-log-reader -f`
2. Review configuration in `.env` file
3. Test database connectivity
4. Verify network connectivity between VMs
5. Check PostgreSQL tables exist and have data
6. Review CPU/memory usage
7. Check disk space

## Next Steps

1. **Customize Dashboard**: Add Zeek visualizations to Streamlit
2. **Implement Alerts**: Create alerting rules based on Zeek events
3. **Build Reports**: Schedule daily/weekly security reports
4. **Threat Intelligence**: Integrate with threat feeds
5. **Machine Learning**: Build anomaly detection models
6. **Automation**: Create automated response workflows

## Files Overview

| File | Purpose |
|------|---------|
| `zeek_log_reader.py` | Main service that reads Zeek logs |
| `zeek_reader_standalone.py` | Standalone version (no backend deps) |
| `backend/app/models.py` | SQLAlchemy models for Zeek tables |
| `backend/app/routes/zeek.py` | FastAPI endpoints for Zeek data |
| `backend/app/database.py` | Database connection management |
| `docker-compose.yml` | Full stack deployment |
| `Dockerfile.zeek-reader` | Zeek service container |
| `ZEEK_README.md` | Quick reference guide |
| `ZEEK_SETUP_GUIDE.md` | Detailed setup instructions |

---

**Version**: 1.0  
**Last Updated**: March 2024  
**Status**: Production Ready
