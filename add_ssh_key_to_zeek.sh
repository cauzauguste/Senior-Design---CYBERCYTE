#!/bin/bash
# add_ssh_key_to_zeek.sh
# This script adds the ED25519 public key to the Zeek VM's authorized_keys

set -e

# Configuration
ZEEK_HOST="35.222.249.202"
ZEEK_USER="zauguste52"
PUBLIC_KEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM0/uleNqaE05oote+mJx3XfwP4EQ7mtKOUey0W7kDlF zauguste52@cis493-fa25-vm1.us-central1-c.c.senior-design-365100.internal"

echo "=========================================="
echo "SSH Key Setup for Zeek VM"
echo "=========================================="
echo "Target: ${ZEEK_USER}@${ZEEK_HOST}"
echo ""

# Check if key already exists locally
if [ ! -f ~/.ssh/id_ed25519 ]; then
    echo "❌ ERROR: ED25519 private key not found at ~/.ssh/id_ed25519"
    echo "Please ensure your SSH keys are properly set up."
    exit 1
fi

echo "✅ Found ED25519 private key at ~/.ssh/id_ed25519"
echo ""

# Option 1: Test if SSH already works
echo "Attempting to connect to Zeek VM..."
if ssh -o BatchMode=yes -o ConnectTimeout=5 -i ~/.ssh/id_ed25519 ${ZEEK_USER}@${ZEEK_HOST} "echo 'Connected successfully!'" 2>/dev/null; then
    echo "✅ SSH connection already works! Key is likely already added."
    exit 0
fi

echo "⏳ SSH connection failed. Attempting to add key..."
echo ""
echo "This script will attempt to add your public key to the Zeek VM."
echo "You have 3 options:"
echo ""
echo "1. If you can SSH to Zeek VM, manually run (from Zeek VM):"
echo "   mkdir -p ~/.ssh"
echo "   echo '$PUBLIC_KEY' >> ~/.ssh/authorized_keys"
echo "   chmod 600 ~/.ssh/authorized_keys"
echo "   chmod 700 ~/.ssh"
echo ""
echo "2. Use Google Cloud Console (browser-based SSH):"
echo "   gcloud compute ssh ${ZEEK_USER}@cis493-fa25-vm1 --zone=us-central1-c"
echo ""
echo "3. If you're on a system with sshpass installed, run:"
echo "   sshpass -p 'YOUR_PASSWORD' ssh-copy-id -i ~/.ssh/id_ed25519.pub ${ZEEK_USER}@${ZEEK_HOST}"
echo ""
echo "After adding the key, test with:"
echo "   ssh -i ~/.ssh/id_ed25519 ${ZEEK_USER}@${ZEEK_HOST} 'ls /opt/zeek/logs/current/'"
echo ""
