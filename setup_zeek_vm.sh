#!/bin/bash
# ============================================================================
# Cybercyte Zeek Log Reader VM - Automated Setup Script
# ============================================================================
# This script should be run on the Zeek Sender VM (35.222.249.202)
# It installs all dependencies and sets up the zeek_log_reader service
# ============================================================================

set -e  # Exit on any error

echo "========================================"
echo "Cybercyte Zeek VM Setup Script"
echo "========================================"
echo ""

# Step 1: Check Python
echo "[1/7] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "  ERROR: Python3 not found. Installing..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv
else
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    echo "  ✓ Python $PYTHON_VERSION found"
fi

# Step 2: Check PostgreSQL tools
echo "[2/7] Checking PostgreSQL client tools..."
if ! command -v psql &> /dev/null; then
    echo "  Installing PostgreSQL client..."
    sudo apt-get install -y postgresql-client
else
    PSQL_VERSION=$(psql --version | head -1)
    echo "  ✓ $PSQL_VERSION found"
fi

# Step 3: Clone or update the project
echo "[3/7] Setting up project directory..."
PROJECT_DIR="/opt/cybercyte"
if [ ! -d "$PROJECT_DIR" ]; then
    echo "  Cloning project to $PROJECT_DIR..."
    sudo git clone https://github.com/cauzauguste/Senior-Design---CYBERCYTE.git "$PROJECT_DIR" || {
        echo "  ERROR: Failed to clone repo. Manual steps:"
        echo "    git clone https://github.com/cauzauguste/Senior-Design---CYBERCYTE.git /opt/cybercyte"
        exit 1
    }
    sudo chown -R $USER:$USER "$PROJECT_DIR"
else
    echo "  ✓ Project directory already exists at $PROJECT_DIR"
fi

cd "$PROJECT_DIR"

# Step 4: Create Python virtual environment
echo "[4/7] Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment already exists"
fi

# Step 5: Install Python dependencies
echo "[5/7] Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt 2>&1 | tail -5
echo "  ✓ Dependencies installed"

# Step 6: Configure environment variables
echo "[6/7] Setting up environment configuration..."
cat > backend/app/.env.zeek_reader.local << 'ENVEOF'
# Zeek Log Reader Configuration
ZEEK_LOG_DIR=/opt/zeek/logs/current
ZEEK_PROCESSED_DIR=/opt/zeek/logs/processed
ZEEK_POLL_INTERVAL=10
POSTGRES_URL=postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db
LOG_LEVEL=INFO
ENVEOF

echo "  ✓ Environment file created: backend/app/.env.zeek_reader.local"

# Step 7: Test connectivity
echo "[7/7] Testing connectivity to Postgres VM..."
pg_isready -h 34.132.194.35 -p 5432 && {
    echo "  ✓ Postgres VM is reachable"
} || {
    echo "  ⚠ WARNING: Postgres VM (34.132.194.35:5432) is NOT reachable"
    echo "    This may be a firewall issue. Check:"
    echo "    1. Your outbound firewall rules (ufw/iptables)"
    echo "    2. GCP firewall rules allowing port 5432"
    echo "    3. Postgres VM pg_hba.conf allows connections from this IP"
}

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Verify Postgres connectivity is working"
echo "2. Start the Zeek log reader with:"
echo "   cd $PROJECT_DIR"
echo "   source venv/bin/activate"
echo "   export POSTGRES_URL='postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db'"
echo "   python3 backend/app/zeek_log_reader.py"
echo ""
echo "3. Or deploy as a systemd service (see DEPLOYMENT_SUMMARY.md)"
echo ""
