# Quick Start Reference Card

## 30-Second Setup

### Database VM
```bash
cd /home/zauguste52/Senior-Design---CYBERCYTE
docker-compose up -d
# Done! PostgreSQL, API, and Dashboard are running
```

### Zeek Sensor VM
```bash
# One-time setup
pip install -r requirements.txt

# Create .env (replace IP!)
echo "POSTGRES_URL=postgresql://postgres:pass@<DB_IP>:5432/cybercyte_db" > .env
echo "ZEEK_LOG_DIR=/opt/zeek/logs/current" >> .env

# Start service
python zeek_reader_standalone.py
```

## URLs

| Service | URL | Purpose |
|---------|-----|---------|
| API | `http://<DB_IP>:8080` | RESTful API |
| API Docs | `http://<DB_IP>:8080/docs` | Interactive documentation |
| Dashboard | `http://<DB_IP>:8501` | Streamlit visualizations |
| Health | `http://<DB_IP>:8080/health` | Health check |

## Common Commands

### Check if running
```bash
docker ps                                    # Database VM
curl http://localhost:8080/health            # Database VM
sudo systemctl status zeek-log-reader        # Zeek VM
```

### View logs
```bash
docker logs cybercyte-postgres               # Database VM
docker logs cybercyte-api                    # Database VM
journalctl -u zeek-log-reader -f             # Zeek VM
```

### Query API
```bash
curl http://localhost:8080/zeek/events/zeek/all
curl http://localhost:8080/zeek/events/zeek/stats
curl http://localhost:8080/zeek/events/zeek/suspicious-ips
```

### Check database
```bash
psql -U postgres -d cybercyte_db
SELECT COUNT(*) FROM zeek_events;
\dt  # List tables
```

## Files Changed

✅ Created:
- `backend/app/zeek_log_reader.py` - Main service
- `backend/app/routes/zeek.py` - API endpoints
- `zeek_reader_standalone.py` - Standalone version
- `Dockerfile.zeek-reader` - Container image
- `ZEEK_README.md` - Quick guide
- `ZEEK_SETUP_GUIDE.md` - Detailed setup
- `DEPLOYMENT_GUIDE.md` - Production guide

✏️ Updated:
- `backend/app/database.py` - Remote PostgreSQL support
- `backend/app/models.py` - Zeek tables (6 new models)
- `backend/app/schemas.py` - Pydantic schemas
- `backend/app/main.py` - Zeek routes
- `requirements.txt` - Added asyncpg, aiokafka
- `conf.env` - Remote PostgreSQL configuration
- `docker-compose.yml` - Multi-service setup

## Database Tables

```
zeek_events          → Generic security events
zeek_connections     → Network connections (conn.log)
zeek_dns            → DNS queries (dns.log)
zeek_files          → File hashing (files.log)
zeek_http           → HTTP traffic (http.log)
zeek_ssl            → SSL/TLS events (ssl.log)
```

## Environment Variables

```bash
POSTGRES_URL=postgresql://user:pass@host:5432/db
ZEEK_LOG_DIR=/opt/zeek/logs/current
ZEEK_PROCESSED_DIR=/opt/zeek/logs/processed
ZEEK_POLL_INTERVAL=10
LOG_LEVEL=INFO
```

## API Endpoints

```
GET /zeek/events/zeek/all
GET /zeek/events/zeek/connections
GET /zeek/events/zeek/dns
GET /zeek/events/zeek/files
GET /zeek/events/zeek/http
GET /zeek/events/zeek/ssl
GET /zeek/events/zeek/stats
GET /zeek/events/zeek/suspicious-ips
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Connection refused | Check PostgreSQL is running and firewall allows 5432 |
| No data | Wait for Zeek logs, check service logs, restart reader |
| High CPU | Increase ZEEK_POLL_INTERVAL, reduce batch size |
| No tables | Run tables creation script or restart service |

## Production Checklist

- [ ] Change default PostgreSQL password
- [ ] Enable SSL/TLS for database
- [ ] Configure firewall rules
- [ ] Set up database backups
- [ ] Enable service auto-restart
- [ ] Configure log rotation
- [ ] Set up monitoring alerts
- [ ] Document custom configurations

---

**Need help?** See DEPLOYMENT_GUIDE.md for detailed instructions.
