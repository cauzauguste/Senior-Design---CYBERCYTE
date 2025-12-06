#!/bin/bash
# ============================================================================
# Cybercyte Backend FastAPI VM - Automated Setup Script
# ============================================================================
# This script should be run on the Backend VM (136.114.77.42)
# It installs all dependencies and sets up the FastAPI service
# ============================================================================

set -e

echo "========================================"
echo "Cybercyte Backend VM Setup Script"
echo "========================================"
echo ""

# Step 1: Check Python
echo "[1/6] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "  ERROR: Python3 not found. Installing..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv
else
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    echo "  ✓ Python $PYTHON_VERSION found"
fi

# Step 2: Check PostgreSQL tools
echo "[2/6] Checking PostgreSQL client tools..."
if ! command -v psql &> /dev/null; then
    echo "  Installing PostgreSQL client..."
    sudo apt-get install -y postgresql-client
else
    PSQL_VERSION=$(psql --version | head -1)
    echo "  ✓ $PSQL_VERSION found"
fi

# Step 3: Setup project directory
echo "[3/6] Setting up project directory..."
PROJECT_DIR="/home/zauguste52/Senior-Design---CYBERCYTE"
if [ ! -d "$PROJECT_DIR" ]; then
    echo "  ERROR: Project directory not found at $PROJECT_DIR"
    exit 1
fi
cd "$PROJECT_DIR"
echo "  ✓ Project directory: $PROJECT_DIR"

# Step 4: Create Python virtual environment
echo "[4/6] Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment already exists"
fi

# Step 5: Install dependencies
echo "[5/6] Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet 2>&1 | tail -3
pip install scapy python-multipart --quiet 2>&1
echo "  ✓ All dependencies installed"

# Step 6: Test connectivity
echo "[6/6] Testing database connectivity..."
export POSTGRES_URL='postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db'
export DATABASE_URL="$POSTGRES_URL"

pg_isready -h 34.132.194.35 -p 5432 && {
    echo "  ✓ Postgres VM is reachable"
} || {
    echo "  ERROR: Cannot reach Postgres VM (34.132.194.35:5432)"
    exit 1
}

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Start FastAPI with:"
echo "   cd $PROJECT_DIR"
echo "   source venv/bin/activate"
echo "   export POSTGRES_URL='postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db'"
echo "   export DATABASE_URL=\$POSTGRES_URL"
echo "   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "2. Or deploy as a systemd service (see DEPLOYMENT_SUMMARY.md)"
echo ""
echo "3. Test the service:"
echo "   curl http://localhost:8000/health"
echo "   curl http://localhost:8000/diagnostics"
echo ""
