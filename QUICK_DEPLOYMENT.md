# Quick Start - Cybercyte Deployment

## Status Summary (December 5, 2025)

✅ **Backend VM (136.114.77.42)**: Ready  
✅ **Postgres VM (34.132.194.35)**: Ready  
⚠️ **Zeek VM (35.222.249.202)**: Needs setup  

---

## Backend VM (136.114.77.42) - Already Running!

FastAPI is **already running** and responding:
```bash
curl http://136.114.77.42:8000/health
# Returns: {"status":"ok"}

curl http://136.114.77.42:8000/diagnostics | jq .
# Shows system info, Python packages, and DB connection status
```

**To redeploy or restart:**
```bash
ssh zauguste52@136.114.77.42
cd ~/Senior-Design---CYBERCYTE
source venv/bin/activate
export POSTGRES_URL='postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db'
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

---

## Zeek VM (35.222.249.202) - Needs Setup

### Automated Setup (Recommended)

1. **Copy setup script to Zeek VM:**
   ```bash
   scp setup_zeek_vm.sh zauguste52@35.222.249.202:/tmp/
   ```

2. **SSH into Zeek VM and run:**
   ```bash
   ssh zauguste52@35.222.249.202
   bash /tmp/setup_zeek_vm.sh
   ```

3. **After setup completes, start the Zeek log reader:**
   ```bash
   cd /opt/cybercyte
   source venv/bin/activate
   export POSTGRES_URL='postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db'
   python3 backend/app/zeek_log_reader.py
   ```

### Manual Setup

If you need to do it step-by-step:

```bash
ssh zauguste52@35.222.249.202

# 1. Install dependencies (if needed)
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv postgresql-client

# 2. Clone project
sudo git clone https://github.com/cauzauguste/Senior-Design---CYBERCYTE.git /opt/cybercyte
sudo chown -R $USER:$USER /opt/cybercyte
cd /opt/cybercyte

# 3. Create venv and install packages
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Test Postgres connection
pg_isready -h 34.132.194.35 -p 5432
psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db -c '\dt'

# 5. Start Zeek log reader
export POSTGRES_URL='postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db'
python3 backend/app/zeek_log_reader.py
```

---

## Postgres VM (34.132.194.35)

If connection issues from Zeek VM occur, check:

```bash
ssh user@34.132.194.35

# Check pg_hba.conf allows connections from Zeek VM
sudo nano /etc/postgresql/*/main/pg_hba.conf
# Add: host    cybercyte_db    postgres    35.222.249.202/32    md5

sudo systemctl reload postgresql

# Verify tables exist
psql -U postgres -d cybercyte_db -c '\dt'
```

---

## Testing & Verification

### From this machine, test Backend VM:
```bash
# Health check
curl http://136.114.77.42:8000/health

# Full diagnostics
curl http://136.114.77.42:8000/diagnostics | jq .

# Swagger UI
curl http://136.114.77.42:8000/docs
```

### From Zeek VM, test Postgres:
```bash
pg_isready -h 34.132.194.35 -p 5432
psql postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db -c 'SELECT 1;'
```

---

## Environment Variables

Both VMs need:
```bash
export POSTGRES_URL='postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db'
export DATABASE_URL="$POSTGRES_URL"
```

These are already set in:
- `backend/app/.env` (Backend VM)
- `backend/app/.env.zeek_reader` (Zeek VM)
- `conf.env` (root config)

---

## Systemd Services (Optional for Production)

See `DEPLOYMENT_SUMMARY.md` for systemd service file templates to auto-start services on reboot.

---

## Documentation Files

- **`DEPLOYMENT_SUMMARY.md`** - Complete deployment guide with systemd services
- **`DEPENDENCY_CHECK_REPORT.md`** - Detailed dependency status report
- **`setup_backend_vm.sh`** - Automated Backend VM setup
- **`setup_zeek_vm.sh`** - Automated Zeek VM setup
- **`ZEEK_README.md`** - Zeek IDS configuration
- **`ZEEK_SETUP_GUIDE.md`** - Zeek setup details
- **`QUICK_START.md`** - Original quick start guide

---

## Next Immediate Actions

1. **SSH into Zeek VM** and run dependency check or setup script
2. **Fix firewall** if Zeek VM → Postgres connection times out
3. **Start Zeek log reader** on Zeek VM
4. **Verify logs** are being written to Postgres

---

Need help? Check the detailed guides above or run the `/diagnostics` endpoint on Backend VM for current system status.
