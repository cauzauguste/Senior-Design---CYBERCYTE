# Zeek Log Reader Setup and Deployment Guide

This guide explains how to set up the PostgreSQL database on one VM and the Zeek log reader on another VM to process Zeek security logs.

## Architecture Overview

```
┌─────────────────────────┐
│  Zeek Sensor VM         │
├─────────────────────────┤
│ Zeek IDS                │
│ ├─ conn.log            │
│ ├─ dns.log             │
│ ├─ http.log            │
│ ├─ ssl.log             │
│ ├─ files.log           │
│ └─ (other logs)        │
│                         │
│ Zeek Log Reader Service │
└────────┬────────────────┘
         │ (reads logs)
         │ (sends data)
         │ via PostgreSQL
         ▼
┌─────────────────────────┐
│ Database/API VM         │
├─────────────────────────┤
│ PostgreSQL              │
│ ├─ zeek_events          │
│ ├─ zeek_connections     │
│ ├─ zeek_dns             │
│ ├─ zeek_files           │
│ ├─ zeek_http            │
│ ├─ zeek_ssl             │
│ └─ (other tables)       │
│                         │
│ FastAPI Backend         │
│ Streamlit Dashboard     │
└─────────────────────────┘
```

## Prerequisites

### On Database/API VM:
- Docker & Docker Compose
- Python 3.10+ (if running without Docker)
- PostgreSQL 13+ (if running without Docker)
- Network access from Zeek VM

### On Zeek Sensor VM:
- Python 3.10+
- Zeek installation (https://zeek.org)
- Network access to PostgreSQL VM
- pip package manager

## Setup Steps

### Step 1: Database VM Setup

#### Option A: Using Docker Compose (Recommended)

```bash
# Clone the repository
cd /home/zauguste52/Senior-Design---CYBERCYTE

# Start all services (PostgreSQL, API, Dashboard)
docker-compose up -d postgres api dashboard

# Verify PostgreSQL is running
docker ps | grep postgres
```

#### Option B: Manual PostgreSQL Installation

```bash
# On Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database user
sudo -u postgres psql -c "CREATE USER postgres WITH PASSWORD 'pass';"
sudo -u postgres psql -c "CREATE DATABASE cybercyte_db OWNER postgres;"
```

### Step 2: Zeek Sensor VM Setup

#### Installation

```bash
# Install Python 3.10+
sudo apt-get update
sudo apt-get install python3.10 python3.10-venv python3-pip

# Create a virtual environment
python3.10 -m venv zeek-reader-env
source zeek-reader-env/bin/activate

# Clone the repository (or copy files from database VM)
git clone <repository-url>
cd Senior-Design---CYBERCYTE

# Install dependencies
pip install -r requirements.txt
```

#### Configuration

Create a `.env` file on the Zeek sensor VM:

```bash
# .env file for Zeek Log Reader
POSTGRES_URL=postgresql://postgres:pass@<DATABASE_VM_IP>:5432/cybercyte_db
ZEEK_LOG_DIR=/opt/zeek/logs/current
ZEEK_PROCESSED_DIR=/opt/zeek/logs/processed
ZEEK_POLL_INTERVAL=10
LOG_LEVEL=INFO
```

Replace `<DATABASE_VM_IP>` with the actual IP address of your database VM.

#### Test Connection

```bash
# Test PostgreSQL connection
python3 << 'EOF'
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("POSTGRES_URL")

async def test():
    pool = await asyncpg.create_pool(url)
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
        print(f"Connection successful: {result}")
    await pool.close()

import asyncio
asyncio.run(test())
EOF
```

#### Run the Zeek Log Reader

```bash
# Option 1: Direct Python execution
python -m backend.app.zeek_log_reader

# Option 2: Using Docker (if Docker is installed)
docker build -f Dockerfile.zeek-reader -t cybercyte-zeek-reader .
docker run -d \
  -e POSTGRES_URL="postgresql://postgres:pass@<DATABASE_VM_IP>:5432/cybercyte_db" \
  -e ZEEK_LOG_DIR="/opt/zeek/logs/current" \
  -v /opt/zeek/logs:/zeek/logs \
  --name zeek-reader \
  cybercyte-zeek-reader
```

### Step 3: Set Up as a Service (Recommended for Production)

#### Using Systemd on Zeek Sensor VM

Create `/etc/systemd/system/zeek-log-reader.service`:

```ini
[Unit]
Description=Zeek Log Reader Service
After=network.target

[Service]
Type=simple
User=zeek
WorkingDirectory=/opt/zeek-reader
Environment="PATH=/opt/zeek-reader/venv/bin"
ExecStart=/opt/zeek-reader/venv/bin/python -m backend.app.zeek_log_reader
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable zeek-log-reader
sudo systemctl start zeek-log-reader
sudo systemctl status zeek-log-reader
```

View logs:

```bash
sudo journalctl -u zeek-log-reader -f
```

#### Using Supervisor on Zeek Sensor VM

Create `/etc/supervisor/conf.d/zeek-log-reader.conf`:

```ini
[program:zeek-log-reader]
directory=/opt/zeek-reader
command=/opt/zeek-reader/venv/bin/python -m backend.app.zeek_log_reader
autostart=true
autorestart=true
stderr_logfile=/var/log/zeek-log-reader.err.log
stdout_logfile=/var/log/zeek-log-reader.out.log
user=zeek
```

Start supervisor:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start zeek-log-reader
```

## Verifying Data Flow

### Check if logs are being read:

```bash
# On Zeek Sensor VM
tail -f /var/log/zeek-log-reader.out.log
```

### Check if data is in PostgreSQL:

```bash
# On Database VM
psql -U postgres -d cybercyte_db

# Inside psql
SELECT COUNT(*) FROM zeek_events;
SELECT COUNT(*) FROM zeek_connections;
SELECT COUNT(*) FROM zeek_dns;

# View recent events
SELECT * FROM zeek_events ORDER BY created_at DESC LIMIT 10;
```

### API Endpoints for Zeek Data

Once the API is running, you can query Zeek data:

```bash
# Get events (add API endpoint for Zeek data)
curl http://<API_VM_IP>:8080/events

# View dashboard
open http://<API_VM_IP>:8501
```

## Supported Zeek Log Types

The service automatically processes:

- **conn.log** - Connection events (stored in `zeek_connections`)
- **dns.log** - DNS queries and responses (stored in `zeek_dns`)
- **http.log** - HTTP requests and responses (stored in `zeek_http`)
- **ssl.log** - SSL/TLS events (stored in `zeek_ssl`)
- **files.log** - File integrity and hashing (stored in `zeek_files`)
- **Other logs** - Generic events (stored in `zeek_events`)

## Troubleshooting

### Issue: "Connection refused" to PostgreSQL

**Solution:**
- Verify PostgreSQL is running on the database VM
- Check firewall rules allow port 5432
- Ensure POSTGRES_URL in .env is correct

### Issue: No logs being processed

**Solution:**
- Check ZEEK_LOG_DIR points to correct Zeek logs location
- Verify Zeek is running: `zeekctl status`
- Check permissions on log directory: `ls -la /opt/zeek/logs/current`
- Review error logs: `tail -f zeek-log-reader.out.log`

### Issue: High memory usage

**Solution:**
- Increase ZEEK_POLL_INTERVAL to reduce polling frequency
- Reduce batch size if processing large files
- Monitor logs: `SELECT COUNT(*) FROM zeek_events;`

## Performance Optimization

### For High-Volume Environments:

1. **Batch Inserts**: Modify `zeek_log_reader.py` to batch insert records
2. **Connection Pooling**: Adjust `max_overflow` in `database.py`
3. **Indexing**: Ensure database indexes are created (done automatically)
4. **Archive Old Logs**: Move/delete old logs from ZEEK_PROCESSED_DIR

### Example Batch Insert

```python
# In zeek_log_reader.py
async def batch_insert_events(events: List[Dict]):
    if not db_pool or not events:
        return
    
    async with db_pool.acquire() as conn:
        await conn.executemany(
            """INSERT INTO zeek_events 
               (log_type, source_ip, dest_ip, source_port, dest_port, 
                protocol, event_text, severity, raw_data, host_id)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
            events
        )
```

## Security Considerations

1. **Change default password** in production
2. **Use SSL/TLS** for PostgreSQL connections
3. **Restrict network access** to database VM
4. **Run service as non-root** user
5. **Monitor service logs** for errors and intrusions
6. **Backup database regularly**
7. **Use strong authentication** if exposing APIs

## Next Steps

1. Create API endpoints for querying Zeek data in `backend/app/routes/zeek.py`
2. Add threat detection rules based on Zeek events
3. Implement alerting system
4. Create custom dashboards in Streamlit
5. Set up data retention policies

## Support

For issues or questions:
1. Check logs: `docker logs cybercyte-zeek-reader`
2. Review configuration in `.env` file
3. Verify network connectivity between VMs
4. Check PostgreSQL tables exist: `\dt` in psql
