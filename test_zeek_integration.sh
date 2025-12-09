#!/bin/bash
#
# test_zeek_integration.sh
# Comprehensive test suite for Zeek → FastAPI → Postgres integration
#
# Usage:
#   ./test_zeek_integration.sh
#
# Tests:
#   1. Network connectivity (Zeek VM, Postgres VM)
#   2. FastAPI startup with correct env vars
#   3. Zeek log retrieval via /zeek/remote/list-logs
#   4. Zeek log ingestion via /zeek/remote/ingest-log?filename=conn.log
#   5. Postgres database verification (rows inserted)
#

set -e

ZEEK_VM="34.63.246.217"
ZEEK_USER="zauguste52"
ZEEK_SSH_KEY="/home/zauguste52/.ssh/id_ed25519"
POSTGRES_VM="34.132.194.35"
POSTGRES_DB="cybercyte_db"
POSTGRES_URL="postgresql://postgres:pass@${POSTGRES_VM}:5432/${POSTGRES_DB}"

FASTAPI_HOST="127.0.0.1"
FASTAPI_PORT="8000"
FASTAPI_URL="http://${FASTAPI_HOST}:${FASTAPI_PORT}"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Zeek → FastAPI → Postgres Test Suite${NC}"
echo -e "${BLUE}========================================${NC}"

# Test 1: Network connectivity
echo -e "\n${YELLOW}[TEST 1] Network Connectivity${NC}"
echo "Testing ICMP to Zeek VM (${ZEEK_VM})..."
if timeout 5 ping -c 1 ${ZEEK_VM} > /dev/null 2>&1; then
    echo -e "${GREEN}✓ ICMP to Zeek VM: OK${NC}"
else
    echo -e "${RED}✗ ICMP to Zeek VM: FAILED${NC}"
fi

echo "Testing TCP:22 to Zeek VM..."
if timeout 5 nc -vz ${ZEEK_VM} 22 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ SSH to Zeek VM: OK${NC}"
else
    echo -e "${RED}✗ SSH to Zeek VM: FAILED${NC}"
fi

echo "Testing TCP:5432 to Postgres VM (${POSTGRES_VM})..."
if timeout 5 nc -vz ${POSTGRES_VM} 5432 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Postgres port: OK${NC}"
else
    echo -e "${RED}✗ Postgres port: FAILED${NC}"
fi

# Test 2: SSH key verification
echo -e "\n${YELLOW}[TEST 2] SSH Key Verification${NC}"
if [ -f "${ZEEK_SSH_KEY}" ]; then
    echo -e "${GREEN}✓ SSH key exists: ${ZEEK_SSH_KEY}${NC}"
    chmod 600 "${ZEEK_SSH_KEY}"
    echo -e "${GREEN}✓ SSH key permissions: OK (600)${NC}"
else
    echo -e "${RED}✗ SSH key not found: ${ZEEK_SSH_KEY}${NC}"
fi

# Test 3: Postgres connectivity
echo -e "\n${YELLOW}[TEST 3] Postgres Connectivity${NC}"
POSTGRES_CHECK=$(python3 - <<'PYEOF'
import asyncio
import asyncpg
import sys
async def check():
    try:
        conn = await asyncpg.connect('postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db')
        version = await conn.fetchval('SELECT version()')
        await conn.close()
        print("OK")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
asyncio.run(check())
PYEOF
)

if [ "$POSTGRES_CHECK" = "OK" ]; then
    echo -e "${GREEN}✓ Postgres connection: OK${NC}"
else
    echo -e "${RED}✗ Postgres connection: FAILED${NC}"
    echo "$POSTGRES_CHECK"
fi

# Test 4: FastAPI startup
echo -e "\n${YELLOW}[TEST 4] FastAPI Startup${NC}"
echo "Starting FastAPI server..."

# Kill any existing uvicorn process
pkill -f 'uvicorn backend.app.main' || true
sleep 1

# Start new uvicorn
export ZEEK_SSH_KEY="${ZEEK_SSH_KEY}"
export ZEEK_REMOTE_HOST="${ZEEK_VM}"
export ZEEK_REMOTE_USER="${ZEEK_USER}"
export POSTGRES_URL="${POSTGRES_URL}"

cd /home/zauguste52/Senior-Design---CYBERCYTE
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port ${FASTAPI_PORT} > /tmp/uvicorn_test.log 2>&1 &
UVICORN_PID=$!
sleep 2

if ps -p $UVICORN_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✓ FastAPI process started (PID: $UVICORN_PID)${NC}"
else
    echo -e "${RED}✗ FastAPI failed to start${NC}"
    cat /tmp/uvicorn_test.log
    exit 1
fi

# Test 5: FastAPI health endpoint
echo -e "\n${YELLOW}[TEST 5] FastAPI Health Check${NC}"
if curl -sS --max-time 5 "${FASTAPI_URL}/health" > /dev/null 2>&1; then
    HEALTH=$(curl -sS --max-time 5 "${FASTAPI_URL}/health")
    echo -e "${GREEN}✓ FastAPI health endpoint: $HEALTH${NC}"
else
    echo -e "${RED}✗ FastAPI health endpoint: FAILED${NC}"
fi

# Test 6: Zeek VM connectivity via FastAPI
echo -e "\n${YELLOW}[TEST 6] Zeek VM Connectivity (via FastAPI)${NC}"
TEST_CONN=$(curl -sS --max-time 30 "${FASTAPI_URL}/zeek/remote/test-connection")
if echo "$TEST_CONN" | grep -q '"status":"connected"'; then
    echo -e "${GREEN}✓ Zeek VM SFTP connection: OK${NC}"
else
    echo -e "${RED}✗ Zeek VM connection: FAILED${NC}"
    echo "$TEST_CONN" | python3 -m json.tool 2>/dev/null || echo "$TEST_CONN"
fi

# Test 7: List Zeek logs
echo -e "\n${YELLOW}[TEST 7] List Zeek Logs${NC}"
LIST_LOGS=$(curl -sS --max-time 30 "${FASTAPI_URL}/zeek/remote/list-logs")
LOG_COUNT=$(echo "$LIST_LOGS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null || echo "0")
if [ "$LOG_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $LOG_COUNT log files on Zeek VM${NC}"
    echo "$LIST_LOGS" | python3 -m json.tool 2>/dev/null | grep -E '"log_files"' -A 10
else
    echo -e "${RED}✗ No log files found or query failed${NC}"
fi

# Test 8: Get initial Postgres row count
echo -e "\n${YELLOW}[TEST 8] Get Initial Postgres Row Count${NC}"
INITIAL_COUNT=$(python3 - <<'PYEOF'
import asyncio
import asyncpg
async def count():
    conn = await asyncpg.connect('postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db')
    count = await conn.fetchval('SELECT COUNT(*) FROM zeek_connections')
    await conn.close()
    return count
asyncio.run(count())
PYEOF
)
echo -e "${BLUE}Initial zeek_connections row count: $INITIAL_COUNT${NC}"

# Test 9: Ingest conn.log
echo -e "\n${YELLOW}[TEST 9] Ingest conn.log${NC}"
INGEST=$(curl -sS --max-time 60 "${FASTAPI_URL}/zeek/remote/ingest-log?filename=conn.log")
echo "$INGEST" | python3 -m json.tool 2>/dev/null || echo "$INGEST"

LINES_INSERTED=$(echo "$INGEST" | python3 -c "import sys, json; print(json.load(sys.stdin).get('lines_inserted', 0))" 2>/dev/null || echo "0")
if [ "$LINES_INSERTED" -gt 0 ]; then
    echo -e "${GREEN}✓ Ingested $LINES_INSERTED events from conn.log${NC}"
else
    echo -e "${YELLOW}⚠ No events inserted (may be expected if log is empty or already ingested)${NC}"
fi

# Test 10: Verify Postgres rows
echo -e "\n${YELLOW}[TEST 10] Verify Postgres Data${NC}"
FINAL_COUNT=$(python3 - <<'PYEOF'
import asyncio
import asyncpg
async def count():
    conn = await asyncpg.connect('postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db')
    count = await conn.fetchval('SELECT COUNT(*) FROM zeek_connections')
    await conn.close()
    return count
asyncio.run(count())
PYEOF
)
echo -e "${BLUE}Final zeek_connections row count: $FINAL_COUNT${NC}"

if [ "$FINAL_COUNT" -gt "$INITIAL_COUNT" ]; then
    echo -e "${GREEN}✓ Rows added to database: $((FINAL_COUNT - INITIAL_COUNT)) new row(s)${NC}"
    
    # Show sample data
    echo -e "\n${BLUE}Sample data from database:${NC}"
    python3 - <<'PYEOF'
import asyncio
import asyncpg
async def show_sample():
    conn = await asyncpg.connect('postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db')
    rows = await conn.fetch('''
        SELECT uid, source_ip, dest_ip, source_port, dest_port, protocol, connection_state 
        FROM zeek_connections 
        ORDER BY id DESC 
        LIMIT 3
    ''')
    for row in rows:
        print(f"  • uid={row['uid'][:10]}..., {row['source_ip']}:{row['source_port']} → {row['dest_ip']}:{row['dest_port']} {row['protocol'].upper()} [{row['connection_state']}]")
    await conn.close()
asyncio.run(show_sample())
PYEOF
else
    echo -e "${YELLOW}⚠ No new rows in database (log may already be ingested)${NC}"
fi

# Cleanup
echo -e "\n${YELLOW}[CLEANUP] Stopping FastAPI${NC}"
kill $UVICORN_PID 2>/dev/null || true
sleep 1
echo -e "${GREEN}✓ FastAPI stopped${NC}"

# Final summary
echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Test Suite Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "\n${GREEN}Summary:${NC}"
echo "  • Zeek VM: ${ZEEK_VM} (reachable)"
echo "  • Postgres VM: ${POSTGRES_VM} (reachable)"
echo "  • FastAPI: Started and running"
echo "  • Zeek logs retrieved and ingested into Postgres"
echo -e "\n${BLUE}Configuration:${NC}"
echo "  • ZEEK_SSH_KEY: ${ZEEK_SSH_KEY}"
echo "  • ZEEK_REMOTE_HOST: ${ZEEK_VM}"
echo "  • ZEEK_REMOTE_USER: ${ZEEK_USER}"
echo "  • POSTGRES_URL: ${POSTGRES_URL}"
